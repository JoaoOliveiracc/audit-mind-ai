"""Retenção de auditorias (spec: .specs/features/audit-retention/spec.md).

Tudo em diretórios temporários — nunca toca ~/.config/auditor.
"""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import TypedDict

import pytest
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from auditor.api.retention import AuditBusyError, AuditNotFoundError, delete_audit
from auditor.api.store import AuditStore


class _S(TypedDict, total=False):
    n: int


def _graph(saver):
    b = StateGraph(_S)
    b.add_node("step", lambda s: {"n": s.get("n", 0) + 1})
    b.add_edge(START, "step")
    b.add_edge("step", END)
    return b.compile(checkpointer=saver)


def _count(saver: SqliteSaver, table: str, thread: str) -> int:
    return saver.conn.execute(
        f"SELECT COUNT(*) FROM {table} WHERE thread_id = ?", (thread,)
    ).fetchone()[0]


class _Runner:
    def __init__(self, done: bool):
        self.done = threading.Event()
        if done:
            self.done.set()


@pytest.fixture
def env(tmp_path: Path):
    store = AuditStore(tmp_path / "meta.sqlite")
    saver = SqliteSaver(sqlite3.connect(str(tmp_path / "cp.sqlite"), check_same_thread=False))
    saver.setup()
    graph = _graph(saver)
    reports = tmp_path / "reports"
    reports.mkdir()

    def make(audit_id: str, status: str = "completed", suffixes=(".md", ".html", ".sarif")):
        store.create(audit_id, "/proj", None, "anthropic", "m")
        graph.invoke({"n": 0}, {"configurable": {"thread_id": audit_id}})
        paths = {}
        for key, suf in zip(("report_md", "report_html", "report_sarif"), suffixes):
            p = reports / f"auditoria-{audit_id}{suf}"
            p.write_text("conteúdo", encoding="utf-8")
            paths[key] = str(p)
        store.update(audit_id, status=status, **paths)
        return [Path(v) for v in paths.values()]

    return store, saver, make


# --- RET-01: exclui metadados, checkpoints e relatórios (só desta auditoria) -------
@pytest.mark.parametrize("status", ["completed", "error"])
def test_delete_finished_audit_removes_everything(env, status):
    store, saver, make = env
    files = make("a1", status)
    make("keep")
    assert _count(saver, "checkpoints", "a1") > 0

    delete_audit("a1", store, saver, {})

    assert store.get("a1") is None
    assert [r["id"] for r in store.list()] == ["keep"]
    assert _count(saver, "checkpoints", "a1") == 0
    assert _count(saver, "writes", "a1") == 0
    assert not any(f.exists() for f in files)
    # outra auditoria intacta
    assert store.get("keep") is not None
    assert _count(saver, "checkpoints", "keep") > 0


# --- RET-02: id inexistente --------------------------------------------------------
def test_delete_unknown_audit_raises_not_found(env):
    store, saver, _ = env
    with pytest.raises(AuditNotFoundError):
        delete_audit("nope", store, saver, {})


# --- RET-03: auditoria viva → recusa sem remover nada ------------------------------
def test_delete_live_audit_is_refused_and_nothing_removed(env):
    store, saver, make = env
    files = make("live", "running")
    registry = {"live": _Runner(done=False)}

    with pytest.raises(AuditBusyError):
        delete_audit("live", store, saver, registry)

    assert store.get("live")["status"] == "running"
    assert _count(saver, "checkpoints", "live") > 0
    assert all(f.exists() for f in files)
    assert "live" in registry


# --- RET-04: órfã (status ativo, sem runner vivo) é excluível ----------------------
@pytest.mark.parametrize("status", ["running", "waiting_input"])
def test_orphan_audit_is_deleted(env, status):
    store, saver, make = env
    files = make("orf", status)

    delete_audit("orf", store, saver, {})

    assert store.get("orf") is None
    assert _count(saver, "checkpoints", "orf") == 0
    assert not any(f.exists() for f in files)


# --- RET-05: runner finalizado sai do registry -------------------------------------
def test_finished_runner_is_removed_from_registry(env):
    store, saver, make = env
    make("fin")
    registry = {"fin": _Runner(done=True), "other": _Runner(done=False)}

    delete_audit("fin", store, saver, registry)

    assert "fin" not in registry
    assert "other" in registry


# --- RET-06: relatório já ausente não impede a exclusão ----------------------------
def test_missing_report_file_is_tolerated(env):
    store, saver, make = env
    files = make("gone")
    files[0].unlink()

    delete_audit("gone", store, saver, {})

    assert store.get("gone") is None
    assert not any(f.exists() for f in files)


# --- RET-07: falha de I/O mantém metadados e checkpoints (re-tentável) -------------
def test_unlink_failure_keeps_metadata_and_checkpoints(env, monkeypatch):
    store, saver, make = env
    make("perm")

    def boom(self, *a, **k):
        raise PermissionError("negado")

    monkeypatch.setattr(Path, "unlink", boom)
    with pytest.raises(OSError):
        delete_audit("perm", store, saver, {})

    assert store.get("perm") is not None
    assert _count(saver, "checkpoints", "perm") > 0


# --- RET-08: só apaga arquivos com sufixo de relatório -----------------------------
def test_only_report_suffixes_are_deleted(env):
    store, saver, make = env
    files = make("suf", suffixes=(".txt", ".html", ".sarif"))

    delete_audit("suf", store, saver, {})

    assert store.get("suf") is None
    assert files[0].exists()           # .txt preservado
    assert not files[1].exists() and not files[2].exists()


# --- CMP-01..03: compactação do banco de checkpoints ------------------------------
from auditor.api.retention import compact_checkpoints  # noqa: E402


def _parent_with_inheriting_subgraph(saver):
    sub = StateGraph(_S)
    sub.add_node("inner", lambda s: {"n": s.get("n", 0) + 10})
    sub.add_edge(START, "inner")
    sub.add_edge("inner", END)
    sub_graph = sub.compile()  # sem checkpointer → herda o do pai (gera namespaces)

    parent = StateGraph(_S)
    parent.add_node("outer", lambda s: sub_graph.invoke(s))
    parent.add_edge(START, "outer")
    parent.add_edge("outer", END)
    return parent.compile(checkpointer=saver)


def _ns_counts(db: Path) -> dict[str, int]:
    conn = sqlite3.connect(str(db))
    try:
        return {
            f"{t}_{k}": conn.execute(
                f"SELECT COUNT(*) FROM {t} WHERE checkpoint_ns {op} ''").fetchone()[0]
            for t in ("checkpoints", "writes") for k, op in (("root", "="), ("sub", "!="))
        }
    finally:
        conn.close()


def test_compact_removes_only_subgraph_rows_and_preserves_state(tmp_path):
    db = tmp_path / "cp.sqlite"
    conn = sqlite3.connect(str(db), check_same_thread=False)
    saver = SqliteSaver(conn)
    saver.setup()
    graph = _parent_with_inheriting_subgraph(saver)
    for tid in ("t1", "t2"):
        graph.invoke({"n": 1}, {"configurable": {"thread_id": tid}})
    before_values = {t: graph.get_state({"configurable": {"thread_id": t}}).values
                     for t in ("t1", "t2")}
    conn.close()  # API parada
    before = _ns_counts(db)
    assert before["checkpoints_sub"] > 0 and before["writes_sub"] > 0  # pré-condição

    stats = compact_checkpoints(db)

    after = _ns_counts(db)
    # CMP-01
    assert after["checkpoints_sub"] == 0 and after["writes_sub"] == 0
    assert after["checkpoints_root"] == before["checkpoints_root"]
    assert after["writes_root"] == before["writes_root"]
    # CMP-02
    assert stats.removed_checkpoints == before["checkpoints_sub"]
    assert stats.removed_writes == before["writes_sub"]
    assert stats.size_before > 0 and 0 < stats.size_after < stats.size_before
    # CMP-03
    reopened = SqliteSaver(sqlite3.connect(str(db), check_same_thread=False))
    graph2 = _parent_with_inheriting_subgraph(reopened)
    for t in ("t1", "t2"):
        assert graph2.get_state({"configurable": {"thread_id": t}}).values == before_values[t]
    assert before_values["t1"] == {"n": 11}


# --- RET-01 (corrida): runner que termina durante a exclusão -----------------------
class _FinishingRunner:
    """Simula o runner concluindo entre a leitura dos metadados e a checagem de 'vivo':
    ao consultar ``done``, grava os relatórios e só então se declara finalizado."""

    def __init__(self, on_finish):
        self._on_finish = on_finish
        self.done = self

    def is_set(self):
        self._on_finish()
        return True


def test_delete_sees_reports_written_by_a_runner_finishing_concurrently(env, tmp_path):
    store, saver, make = env
    make("race", "running", suffixes=())  # sem relatórios registrados ainda
    late = tmp_path / "reports" / "auditoria-race.html"

    def finish():
        late.write_text("trecho de código", encoding="utf-8")
        store.update("race", status="completed", report_html=str(late))

    delete_audit("race", store, saver, {"race": _FinishingRunner(finish)})

    assert store.get("race") is None
    assert not late.exists()
