"""Teto da penalidade de pacotes vulneráveis na pontuação (spec: .specs/features/dependency-score-cap — G49)."""
from __future__ import annotations

import io
import random

import pytest
from langchain_core.messages import AIMessage
from rich.console import Console

from auditor import chat, cli, scoring
from auditor.nodes import synthesis
from auditor.report.renderer import build_context, render_html, render_markdown
from auditor.state import DimensionResult

_W = {"critical": 40, "high": 20, "medium": 8, "low": 3, "info": 0}   # pesos da spec


def osv(sev: str, name: str = "pkg") -> dict:
    return {"dimension": "dependencies", "source": "osv", "severity": sev, "title": f"{name}@1.0.0"}


def eol(sev: str) -> dict:
    return {"dimension": "dependencies", "source": "endoflife", "severity": sev, "title": "Runtime"}


def llm(sev: str, dimension: str = "security") -> dict:
    return {"dimension": dimension, "severity": sev, "title": "x"}


# --- SCORE-01/03/04: exemplos normativos --------------------------------------------------
@pytest.mark.parametrize("findings, expected", [
    ([osv("high")] * 5, 60),
    ([osv("high")], 80),
    ([osv("high")] * 2, 60),                                           # soma exata 40, sem teto
    ([osv("critical")] + [osv("high")] * 3, 60),
    ([llm("critical")] + [osv("high")] * 5, 20),
    ([osv("high"), eol("high"), llm("high")], 40),
    ([osv("info")] * 6, 100),
], ids=["5high", "1high", "2high-boundary", "crit+3high", "llmcrit+5high", "mixed", "6info"])
def test_score01_normative_examples(findings, expected):
    assert scoring.compute_health_score(findings) == expected


def test_score04_cap_constant_and_breakdown():
    assert scoring.DEPENDENCY_PENALTY_CAP == 40
    dp = scoring.dependency_penalty([osv("high")] * 5 + [osv("info")] * 3 + [llm("critical"), eol("high")])
    assert (dp.applied, dp.uncapped, dp.packages) == (40, 100, 5)     # info não conta em N
    assert scoring.dependency_penalty([llm("high")]) == scoring.DependencyPenalty(0, 0, 0)


def test_score03_runtime_and_llm_dependencies_keep_full_weight():
    assert scoring.compute_health_score([eol("high")] * 5) == 0
    assert scoring.compute_health_score([llm("high", "dependencies")] * 5) == 0
    assert scoring.compute_health_score([osv("high")] * 5 + [eol("high")] * 2) == 20


def test_score01_missing_or_unknown_severity_weighs_zero():
    assert scoring.compute_health_score([{"source": "osv"}, {"source": "osv", "severity": "bogus"},
                                         {"severity": None}]) == 100
    assert scoring.dependency_penalty([{"source": "osv", "severity": "bogus"}]).packages == 0


def test_score02_regression_without_osv_generated():
    rng = random.Random(4902)
    sevs = [*_W, None, "bogus"]
    for _ in range(500):
        findings = [{"severity": rng.choice(sevs), **({"source": "endoflife"} if rng.random() < .3 else {})}
                    for _ in range(rng.randint(0, 12))]
        old = max(0, 100 - min(100, sum(_W.get(f["severity"], 0) for f in findings)))
        assert scoring.compute_health_score(findings) == old


def test_edge_floor_when_non_osv_alone_zeroes():
    assert scoring.compute_health_score([llm("critical")] * 3 + [osv("high")]) == 0
    score, dp = scoring.score_with_breakdown([llm("critical")] * 3 + [osv("high")])
    assert score == 0                                                  # piso inalterado
    assert scoring.dependency_penalty_line(dp._asdict()) == \
        "Pacotes vulneráveis (OSV): \u221220 pontos (1 pacote(s))"     # a linha ainda mostra a parcela


# --- SCORE-05: achado do LLM com "source": "osv" não entra no grupo com teto ---------------
def test_score05_llm_cannot_join_capped_group():
    raw = {"dimension": "security", "summary": "s", "findings": [
        {"dimension": "security", "title": f"t{i}", "severity": "high", "description": "d",
         "recommendation": "r", "source": "osv"} for i in range(5)]}
    stored = [f.model_dump(mode="json") for f in DimensionResult.model_validate(raw).findings]
    assert all("source" not in f for f in stored)
    assert scoring.compute_health_score(stored) == 0                   # peso cheio: 5 × 20
    assert scoring.dependency_penalty(stored).uncapped == 0


# --- EXPL-01/02: texto exato da linha -----------------------------------------------------
@pytest.mark.parametrize("findings, line", [
    ([osv("high")], "Pacotes vulneráveis (OSV): −20 pontos (1 pacote(s))"),
    ([osv("high")] * 2, "Pacotes vulneráveis (OSV): −40 pontos (2 pacote(s))"),
    ([osv("high")] * 5, "Pacotes vulneráveis (OSV): −40 pontos (5 pacote(s)) — teto de 40 "
                        "aplicado; sem teto seriam −100"),
])
def test_expl01_line_text(findings, line):
    dp = scoring.dependency_penalty(findings)
    assert scoring.dependency_penalty_line(dp._asdict()) == line


@pytest.mark.parametrize("stored", [None, {"applied": 0, "uncapped": 0, "packages": 0}, {}])
def test_expl02_no_line_without_penalty(stored):
    assert scoring.dependency_penalty_line(stored) is None


# --- SCORE-06 / EXPL-03: síntese grava o detalhamento e o injeta no prompt ------------------
class _CaptureLLM:
    def __init__(self):
        self.messages = None

    def invoke(self, messages):
        self.messages = messages
        return AIMessage(content="resumo")


def _run_synthesis(monkeypatch, findings):
    fake = _CaptureLLM()
    monkeypatch.setattr(synthesis, "get_llm", lambda *a, **k: fake)
    out = synthesis.synthesis_node({"findings": findings})
    return out, fake.messages[-1].content


def test_score06_synthesis_stores_breakdown_and_prompt_line(monkeypatch):
    out, prompt = _run_synthesis(monkeypatch, [osv("high")] * 5 + [llm("medium")])
    assert out["health_score"] == 52
    assert out["dependency_penalty"] == {"applied": 40, "uncapped": 100, "packages": 5}
    lines = prompt.splitlines()
    i = lines.index("Pontuação de saúde calculada: 52/100")
    assert lines[i + 1] == scoring.dependency_penalty_line(out["dependency_penalty"])


def test_expl03_prompt_unchanged_without_penalty(monkeypatch):
    out, prompt = _run_synthesis(monkeypatch, [llm("high")])
    assert out["dependency_penalty"] == {"applied": 0, "uncapped": 0, "packages": 0}
    lines = prompt.splitlines()
    i = lines.index("Pontuação de saúde calculada: 80/100")
    assert lines[i + 1] == ""                                          # como hoje: linha em branco
    assert "Pacotes vulneráveis" not in prompt


# --- EXPL-01 (posição) / EXPL-02 / EXPL-04 / SCORE-06 (ausente) nas saídas ------------------
_FIVE = [osv("high", f"p{i}") for i in range(5)]
_CAPPED = {"applied": 40, "uncapped": 100, "packages": 5}
_LINE = ("Pacotes vulneráveis (OSV): −40 pontos (5 pacote(s)) — teto de 40 aplicado; "
         "sem teto seriam −100")


def _state(dp=None, score=60, findings=_FIVE):
    s = {"project_path": "/p", "health_score": score, "findings": list(findings), "executive_summary": "r"}
    if dp is not None:
        s["dependency_penalty"] = dp
    return s


def test_expl01_markdown_placement():
    md = render_markdown(build_context(_state(_CAPPED), "2026-11-10"))
    lines = md.splitlines()
    i = lines.index("- **Pontuação de saúde:** 60/100")
    assert lines[i + 1] == f"- {_LINE}"


def test_expl01_html_placement_under_label():
    html = render_html(build_context(_state(_CAPPED), "2026-11-10"))
    label = html.index('<div style="font-weight:600">Pontuação de saúde</div>')
    line = html.index(_LINE)
    assert label < line < html.index("achado(s) no total")
    between = html[label + len('<div style="font-weight:600">Pontuação de saúde</div>'):line]
    assert "<div" in between and "</div>" not in between               # elemento logo abaixo do rótulo


def _cli_out(monkeypatch, state) -> str:
    out = io.StringIO()
    monkeypatch.setattr(cli, "console", Console(file=out, width=200, color_system=None))
    cli._print_summary(state)
    return out.getvalue()


def test_expl01_cli_panel_line(monkeypatch):
    lines = [ln.strip("│ ").rstrip() for ln in _cli_out(monkeypatch, _state(_CAPPED)).splitlines()]
    i = next(k for k, ln in enumerate(lines) if ln.startswith("Pontuação de saúde: 60/100"))
    assert lines[i + 1].rstrip(" │") == _LINE


def test_expl04_chat_context_line():
    lines = chat.build_report_context(_state(_CAPPED)).splitlines()
    i = lines.index("Pontuação de saúde: 60/100")
    assert lines[i + 1] == _LINE


@pytest.mark.parametrize("dp", [None, {"applied": 0, "uncapped": 0, "packages": 0}])
def test_expl02_outputs_identical_without_penalty(monkeypatch, dp):
    base, other = _state(None, 80, [llm("high")]), _state(dp, 80, [llm("high")])
    assert render_markdown(build_context(base, "t")) == render_markdown(build_context(other, "t"))
    assert render_html(build_context(base, "t")) == render_html(build_context(other, "t"))
    assert chat.build_report_context(base) == chat.build_report_context(other)
    assert _cli_out(monkeypatch, base) == _cli_out(monkeypatch, other)


def test_expl02_html_only_adds_the_line():
    with_line = render_html(build_context(_state(_CAPPED), "t"))
    without = render_html(build_context(_state(None), "t"))
    assert with_line != without and _LINE not in without
    start = with_line.index(_LINE)
    open_tag = with_line.rindex("<div", 0, start)
    close = with_line.index("</div>", start) + len("</div>")
    removed = with_line[:open_tag] + with_line[close:]
    assert removed.split() == without.split()                          # nada além da linha muda


def test_score06_pre_g49_state_never_recomputes(monkeypatch):
    """Auditoria da era G48 (nota 0 sem teto, sem campo) não ganha linha de "teto aplicado"."""
    state = _state(None, 0, _FIVE)
    md = render_markdown(build_context(state, "t"))
    html = render_html(build_context(state, "t"))
    for text in (md, html, chat.build_report_context(state), _cli_out(monkeypatch, state)):
        assert "Pacotes vulneráveis" not in text
    assert "- **Pontuação de saúde:** 0/100" in md


# --- review fixes (code-review G49) ------------------------------------------------------
def test_review_suffix_comes_from_stored_value_not_current_constant(monkeypatch):
    stored = {"applied": 40, "uncapped": 60, "packages": 3}
    monkeypatch.setattr(scoring, "DEPENDENCY_PENALTY_CAP", 60)          # teto mudou depois da auditoria
    assert scoring.dependency_penalty_line(stored) == (
        "Pacotes vulneráveis (OSV): −40 pontos (3 pacote(s)) — teto de 40 aplicado; "
        "sem teto seriam −60")


def test_review_score_and_breakdown_from_one_computation():
    findings = [osv("high")] * 3 + [llm("low")]
    score, dp = scoring.score_with_breakdown(findings)
    assert (score, dp) == (scoring.compute_health_score(findings), scoring.dependency_penalty(findings))
    assert score == 100 - 3 - dp.applied


def test_review_scanner_source_tag_is_the_capped_group():
    import inspect

    from auditor.vulnscan import models, scanner
    assert scoring.OSV_SOURCE is models.OSV_SOURCE
    assert '"osv"' not in inspect.getsource(scanner)                      # sem literal duplicado
