"""Helpers compartilhados (spec: .specs/features/dedup-and-test-isolation — DUP-01..03)."""
from __future__ import annotations

import io
import re
from pathlib import Path
from typing import TypedDict

import pytest
from langgraph.graph import END, START, StateGraph

import auditor
from auditor import events
from auditor.graph import build_graph

SRC = Path(auditor.__file__).parent


# --- DUP-01: um único emit ----------------------------------------------------------
def test_dup01_emit_is_a_silent_noop_outside_a_run():
    assert events.emit({"type": "x"}) is None


def test_dup01_emit_reaches_the_custom_stream_inside_a_run():
    class _S(TypedDict, total=False):
        n: int

    def node(_s):
        events.emit({"type": "probe", "value": 42})
        return {"n": 1}

    b = StateGraph(_S)
    b.add_node("n", node)
    b.add_edge(START, "n")
    b.add_edge("n", END)
    chunks = list(b.compile().stream({}, stream_mode="custom"))
    assert chunks == [{"type": "probe", "value": 42}]


def test_dup01_dup02_no_copies_left_outside_events():
    offenders = []
    for path in SRC.rglob("*.py"):
        if path.name == "events.py":
            continue
        text = path.read_text(encoding="utf-8")
        # Só definições de MÓDULO (coluna 0): `AuditRunner._emit` é outro conceito (log do SSE).
        for needle in ("\ndef _emit(", "from langgraph.config import get_stream_writer"):
            if needle in "\n" + text:
                offenders.append(f"{path.relative_to(SRC)}: {needle.strip()}")
        if re.search(r"^_?NODE_(LABELS|ICONS)\s*(:[^=\n]*)?=", text, re.M):   # inclui forma anotada
            offenders.append(f"{path.relative_to(SRC)}: NODE_LABELS/ICONS")
    assert offenders == []


# --- DUP-02: rótulos para todos os nós do grafo -------------------------------------
def test_dup02_labels_cover_every_graph_node():
    nodes = set(build_graph().get_graph().nodes) - {"__start__", "__end__"}
    assert set(events.NODE_LABELS) == nodes
    assert set(events.NODE_ICONS) == nodes


def test_dup02_api_phase_events_use_the_shared_labels():
    from auditor.api.runner import AuditRunner

    class _G:
        def stream(self, *a, **k):
            yield ("updates", {"discovery": {}})

        def get_state(self, config):
            return type("S", (), {"values": {"findings": []}})()

    class _Store:
        def update(self, *a, **k):
            pass

    runner = AuditRunner("t", _G(), _Store(), {})
    runner.start()
    assert runner.done.wait(5)
    phase = next(e for e in runner.log if e["event"] == "phase")
    assert phase["data"]["label"] == events.NODE_LABELS["discovery"]


# --- DUP-03: uma única contagem por severidade --------------------------------------
from auditor import scoring  # noqa: E402

_F = [{"severity": "high"}, {"severity": "high"}, {"severity": "low"}]


def test_dup03_counts_with_zeros_lists_all_five_in_order():
    assert scoring.severity_counts(_F) == {"critical": 0, "high": 2, "medium": 0, "low": 1, "info": 0}
    assert list(scoring.severity_counts(_F)) == ["critical", "high", "medium", "low", "info"]


def test_dup03_counts_without_zeros_lists_only_present():
    assert scoring.severity_counts(_F, include_zero=False) == {"high": 2, "low": 1}


def test_dup03_missing_severity_counts_as_info():
    assert scoring.severity_counts([{}], include_zero=False) == {"info": 1}


def test_dup03_old_entry_points_delegate_to_scoring():
    from auditor.api.runner import _counts
    from auditor.nodes import synthesis

    assert synthesis.severity_counts is scoring.severity_counts
    assert synthesis.compute_health_score is scoring.compute_health_score
    assert _counts(_F) == scoring.severity_counts(_F, include_zero=False)


def test_dup03_no_other_counting_loops():
    offenders = [str(p.relative_to(SRC)) for p in SRC.rglob("*.py")
                 if p.name != "scoring.py" and any(n in p.read_text(encoding="utf-8")
                                                   for n in ("counts.get(", "Counter("))]
    assert offenders == []



# --- Fix loop 1: comportamento em cada ponto de uso (DUP-02 CLI, DUP-03 relatório/CLI) ---
from rich.console import Console  # noqa: E402

from auditor import cli  # noqa: E402
from auditor.report.renderer import build_context  # noqa: E402

_MIXED = [{"severity": "high"}, {"severity": "high"}, {"severity": None}, {"severity": ""}, {}]


@pytest.mark.parametrize("value", [None, ""])
def test_dup03_none_or_empty_severity_counts_as_info(value):
    assert scoring.severity_counts([{"severity": value}], include_zero=False) == {"info": 1}


def test_dup03_report_context_counts_use_shared_counting():
    ctx = build_context({"findings": _MIXED}, generated_at="x")
    assert ctx["counts"] == {"critical": 0, "high": 2, "medium": 0, "low": 0, "info": 3}


def _capture_cli(monkeypatch) -> io.StringIO:
    out = io.StringIO()
    monkeypatch.setattr(cli, "console", Console(file=out, width=200, color_system=None))
    return out


def test_dup03_cli_summary_table_uses_shared_counting(monkeypatch):
    out = _capture_cli(monkeypatch)
    cli._print_summary({"health_score": 50, "findings": _MIXED})
    rows = {line.split()[1]: line.split()[3] for line in out.getvalue().splitlines()
            if len(line.split()) == 5 and line.split()[1] in scoring.severity_counts([])}
    assert rows == {"critical": "0", "high": "2", "medium": "0", "low": "0", "info": "3"}


def test_dup02_cli_phase_lines_use_shared_labels(monkeypatch):
    out = _capture_cli(monkeypatch)

    class _G:
        def stream(self, *a, **k):
            yield {"planning": {}}
            yield {"report": {}}

    assert cli._run(_G(), {}, {}) is None
    text = out.getvalue()
    for node in ("planning", "report"):
        assert f"{events.NODE_ICONS[node]} {events.NODE_LABELS[node]}" in text
