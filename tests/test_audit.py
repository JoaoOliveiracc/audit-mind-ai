"""Testes do audit_node paralelo (offline; investigador mockado, sem LLM)."""
import time

from auditor.nodes import audit
from auditor.state import DimensionResult, Finding


class _Settings:
    max_concurrent_investigators = 4
    max_investigator_steps = 10


def _finding(dim: str) -> Finding:
    return Finding(
        dimension=dim, title=f"f-{dim}", severity="low",
        description="d", recommendation="r",
    )


def _patch_common(monkeypatch):
    monkeypatch.setattr(audit, "get_settings", lambda: _Settings())
    monkeypatch.setattr(audit, "get_llm", lambda *a, **k: object())
    monkeypatch.setattr(audit, "make_project_tools", lambda root, settings: [])


def test_aggregates_in_plan_order_despite_completion_order(tmp_path, monkeypatch):
    _patch_common(monkeypatch)
    # 'security' dorme mais → conclui por último, mesmo sendo o 1º do plano.
    delays = {"security": 0.05, "quality": 0.02, "testing": 0.0}

    def fake(dim, state, tools, llm, settings):
        time.sleep(delays.get(dim, 0))
        return DimensionResult(dimension=dim, summary=f"resumo {dim}", findings=[_finding(dim)])

    monkeypatch.setattr(audit, "_investigate_dimension", fake)

    plan = ["security", "quality", "testing"]
    out = audit.audit_node({"project_path": str(tmp_path), "plan": {"dimensions": plan}})

    assert out["status"] == "audited"
    # ordem determinística = ordem do plano (não a ordem de conclusão)
    assert [f["dimension"] for f in out["findings"]] == plan
    assert [s["dimension"] for s in out["dimension_summaries"]] == plan


def test_runs_concurrently(tmp_path, monkeypatch):
    _patch_common(monkeypatch)
    # 4 dimensões, cada uma "demora" 0.1s. Em paralelo (4 workers) ~0.1s;
    # sequencial seria ~0.4s. Damos folga generosa para evitar flakiness.
    def fake(dim, state, tools, llm, settings):
        time.sleep(0.1)
        return DimensionResult(dimension=dim, summary="s", findings=[])

    monkeypatch.setattr(audit, "_investigate_dimension", fake)

    plan = ["security", "quality", "testing", "performance"]
    start = time.monotonic()
    audit.audit_node({"project_path": str(tmp_path), "plan": {"dimensions": plan}})
    elapsed = time.monotonic() - start
    assert elapsed < 0.35, f"esperava execução paralela, levou {elapsed:.2f}s"


def test_dimension_failure_is_isolated(tmp_path, monkeypatch):
    _patch_common(monkeypatch)

    def fake(dim, state, tools, llm, settings):
        if dim == "quality":
            raise RuntimeError("boom")
        return DimensionResult(dimension=dim, summary=f"ok {dim}", findings=[_finding(dim)])

    monkeypatch.setattr(audit, "_investigate_dimension", fake)

    plan = ["security", "quality", "testing"]
    out = audit.audit_node({"project_path": str(tmp_path), "plan": {"dimensions": plan}})

    # dimensões saudáveis continuam; a que falhou não aparece nos findings
    assert [f["dimension"] for f in out["findings"]] == ["security", "testing"]
    summaries = {s["dimension"]: s["summary"] for s in out["dimension_summaries"]}
    assert summaries["quality"].startswith("Falha na análise")
    assert len(out["dimension_summaries"]) == 3


def test_none_result_yields_placeholder_summary(tmp_path, monkeypatch):
    _patch_common(monkeypatch)
    monkeypatch.setattr(audit, "_investigate_dimension", lambda *a, **k: None)

    out = audit.audit_node({"project_path": str(tmp_path), "plan": {"dimensions": ["security"]}})
    assert out["findings"] == []
    assert out["dimension_summaries"][0]["summary"] == "Sem resultado estruturado."


def test_empty_plan(tmp_path, monkeypatch):
    _patch_common(monkeypatch)
    out = audit.audit_node({"project_path": str(tmp_path), "plan": {"dimensions": []}})
    assert out == {"findings": [], "dimension_summaries": [], "status": "audited"}
