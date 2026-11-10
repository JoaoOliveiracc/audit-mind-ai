"""CLI `auditor db compact` (spec: .specs/features/audit-retention/spec.md — CMP-04)."""
from __future__ import annotations

import sqlite3
from typing import TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from typer.testing import CliRunner

from auditor.cli import app

runner = CliRunner()


class _S(TypedDict, total=False):
    n: int


def _db_with_subgraph_rows(path):
    sub = StateGraph(_S)
    sub.add_node("inner", lambda s: {"n": 1})
    sub.add_edge(START, "inner")
    sub.add_edge("inner", END)
    sub_graph = sub.compile()
    parent = StateGraph(_S)
    parent.add_node("outer", lambda s: sub_graph.invoke(s))
    parent.add_edge(START, "outer")
    parent.add_edge("outer", END)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    saver = SqliteSaver(conn)
    saver.setup()
    parent.compile(checkpointer=saver).invoke({"n": 0}, {"configurable": {"thread_id": "t"}})
    removed = conn.execute("SELECT COUNT(*) FROM checkpoints WHERE checkpoint_ns != ''").fetchone()[0]
    conn.close()
    return removed


def test_db_compact_success_prints_counts_and_exits_0(tmp_path):
    db = tmp_path / "cp.sqlite"
    expected = _db_with_subgraph_rows(db)
    assert expected > 0

    result = runner.invoke(app, ["db", "compact", "--db", str(db)])

    assert result.exit_code == 0, result.output
    assert f"Checkpoints de sub-agentes removidos: {expected}" in result.output
    assert "Tamanho:" in result.output


def test_db_compact_missing_db_exits_0_with_message(tmp_path):
    result = runner.invoke(app, ["db", "compact", "--db", str(tmp_path / "nao-existe.sqlite")])

    assert result.exit_code == 0
    assert "Nada a compactar" in result.output


def test_db_compact_locked_db_exits_1_and_asks_to_stop_api(tmp_path):
    db = tmp_path / "cp.sqlite"
    _db_with_subgraph_rows(db)
    holder = sqlite3.connect(str(db))
    holder.execute("BEGIN EXCLUSIVE")
    try:
        result = runner.invoke(app, ["db", "compact", "--db", str(db)])
    finally:
        holder.rollback()
        holder.close()

    assert result.exit_code == 1
    assert "pare a API" in result.output
