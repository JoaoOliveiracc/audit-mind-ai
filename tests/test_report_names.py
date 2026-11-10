"""Nomes únicos de relatório (spec: .specs/features/history-polish — REP-01..05)."""
from __future__ import annotations

import re
from datetime import datetime as real_datetime

import pytest

from auditor.nodes import report as report_node_mod
from auditor.report import renderer

STAMP = "20261110-101500"
STATE = {"project_path": "/proj", "findings": [], "health_score": 100, "executive_summary": "ok"}


@pytest.fixture
def frozen(monkeypatch):
    class _Frozen(real_datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 11, 10, 10, 15, 0)

    monkeypatch.setattr(renderer, "datetime", _Frozen)


def _names(paths):
    return [p.name for p in paths]


# --- REP-01 -------------------------------------------------------------------------
def test_names_have_timestamp_and_id8(tmp_path, frozen):
    paths = renderer.write_reports(STATE, tmp_path, run_id="abcdef1234567890")
    assert _names(paths) == [f"auditoria-{STAMP}-abcdef12.md", f"auditoria-{STAMP}-abcdef12.html",
                             f"auditoria-{STAMP}-abcdef12.sarif"]
    assert all(p.parent == tmp_path for p in paths)


# --- REP-02 -------------------------------------------------------------------------
def test_two_runs_in_same_second_do_not_touch_each_other(tmp_path, frozen):
    first = renderer.write_reports(STATE, tmp_path, run_id="aaaaaaaa1111")
    before = [p.read_bytes() for p in first]
    second = renderer.write_reports({**STATE, "executive_summary": "outro"}, tmp_path,
                                    run_id="bbbbbbbb2222")

    assert set(_names(first)).isdisjoint(_names(second))
    assert [p.read_bytes() for p in first] == before


# --- REP-03 -------------------------------------------------------------------------
def test_existing_name_is_never_overwritten(tmp_path, frozen):
    first = renderer.write_reports(STATE, tmp_path, run_id="samesame")
    before = first[0].read_text(encoding="utf-8")
    again = renderer.write_reports({**STATE, "executive_summary": "outro"}, tmp_path,
                                   run_id="samesame")

    assert _names(again) == [f"auditoria-{STAMP}-samesame-2.md",
                             f"auditoria-{STAMP}-samesame-2.html",
                             f"auditoria-{STAMP}-samesame-2.sarif"]
    assert first[0].read_text(encoding="utf-8") == before


def test_partial_collision_moves_all_three_to_next_suffix(tmp_path, frozen):
    (tmp_path / f"auditoria-{STAMP}-onlysarf.sarif").write_text("antigo", encoding="utf-8")
    paths = renderer.write_reports(STATE, tmp_path, run_id="onlysarf")
    assert _names(paths)[0] == f"auditoria-{STAMP}-onlysarf-2.md"
    assert (tmp_path / f"auditoria-{STAMP}-onlysarf.sarif").read_text(encoding="utf-8") == "antigo"


# --- REP-04 -------------------------------------------------------------------------
@pytest.mark.parametrize("run_id", [None, "", "../--//!!"])
def test_missing_or_non_alnum_id_uses_random_hex(tmp_path, frozen, run_id):
    paths = renderer.write_reports(STATE, tmp_path, run_id=run_id)
    assert re.fullmatch(rf"auditoria-{STAMP}-[0-9a-f]{{8}}\.md", paths[0].name)


def test_unsafe_chars_are_dropped_and_files_stay_inside(tmp_path, frozen):
    paths = renderer.write_reports(STATE, tmp_path, run_id="../a/b-c_d.e/f9")
    assert _names(paths)[0] == f"auditoria-{STAMP}-abcdef9.md"
    assert all(p.parent == tmp_path for p in paths)


# --- REP-05 -------------------------------------------------------------------------
def test_report_node_uses_thread_id_from_config(tmp_path, frozen, monkeypatch):
    class _S:
        output_dir = str(tmp_path)

    monkeypatch.setattr(report_node_mod, "get_settings", lambda: _S())
    out = report_node_mod.report_node(dict(STATE), {"configurable": {"thread_id": "1234abcd5678"}})

    assert out["report_html_path"].endswith(f"auditoria-{STAMP}-1234abcd.html")
    assert out["report_sarif_path"].endswith(f"auditoria-{STAMP}-1234abcd.sarif")


# --- REP-03 (gravação exclusiva por si só): mesmo se a checagem falhar, nada é sobrescrito --
def test_exclusive_create_never_overwrites_even_if_free_base_is_wrong(tmp_path, frozen,
                                                                       monkeypatch):
    existing = tmp_path / f"auditoria-{STAMP}-racerace.md"
    existing.write_text("original", encoding="utf-8")
    monkeypatch.setattr(renderer, "_free_base", lambda output_dir, base: base)  # simula corrida

    with pytest.raises(FileExistsError):
        renderer.write_reports(STATE, tmp_path, run_id="racerace")
    assert existing.read_text(encoding="utf-8") == "original"
