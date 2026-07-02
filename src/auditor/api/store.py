"""Persistência: checkpointer do grafo (SqliteSaver) + metadados de auditorias."""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from langgraph.checkpoint.sqlite import SqliteSaver


def _db_dir() -> Path:
    path = Path.home() / ".config" / "auditor"
    path.mkdir(parents=True, exist_ok=True)
    return path


CHECKPOINT_DB = _db_dir() / "audits-checkpoints.sqlite"
META_DB = _db_dir() / "audits.sqlite"


def build_checkpointer() -> SqliteSaver:
    """Cria o checkpointer SQLite (compartilhável entre threads)."""
    conn = sqlite3.connect(str(CHECKPOINT_DB), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    saver = SqliteSaver(conn)
    saver.setup()
    return saver


class AuditStore:
    """Armazena metadados de auditorias em SQLite (thread-safe via lock)."""

    def __init__(self, db_path: Path = META_DB) -> None:
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._lock = threading.Lock()
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audits (
                id TEXT PRIMARY KEY,
                project_path TEXT NOT NULL,
                goal TEXT,
                provider TEXT,
                model TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                health_score INTEGER,
                counts_json TEXT,
                report_html TEXT,
                report_md TEXT,
                error TEXT
            )
            """
        )
        self._conn.commit()

    def create(self, audit_id: str, project_path: str, goal: Optional[str],
               provider: Optional[str], model: Optional[str]) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO audits (id, project_path, goal, provider, model, status, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (audit_id, project_path, goal, provider, model, "running",
                 datetime.now(timezone.utc).isoformat(timespec="seconds")),
            )
            self._conn.commit()

    def update(self, audit_id: str, **fields: Any) -> None:
        if not fields:
            return
        if "counts" in fields:
            fields["counts_json"] = json.dumps(fields.pop("counts"), ensure_ascii=False)
        cols = ", ".join(f"{k} = ?" for k in fields)
        with self._lock:
            self._conn.execute(
                f"UPDATE audits SET {cols} WHERE id = ?",
                (*fields.values(), audit_id),
            )
            self._conn.commit()

    def get(self, audit_id: str) -> Optional[dict]:
        with self._lock:
            cur = self._conn.execute("SELECT * FROM audits WHERE id = ?", (audit_id,))
            row = cur.fetchone()
            cols = [d[0] for d in cur.description]
        return self._row_to_dict(cols, row) if row else None

    def list(self) -> list[dict]:
        with self._lock:
            cur = self._conn.execute("SELECT * FROM audits ORDER BY created_at DESC")
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
        return [self._row_to_dict(cols, r) for r in rows]

    @staticmethod
    def _row_to_dict(cols: list[str], row: tuple) -> dict:
        data = dict(zip(cols, row))
        counts = data.pop("counts_json", None)
        data["counts"] = json.loads(counts) if counts else None
        return data
