"""Retenção de auditorias: exclusão manual e compactação do banco de checkpoints.

Funções puras com dependências injetadas (store, checkpointer, registry) — a rota
e a CLI ficam finas e a lógica é testável sem a app nem o diretório do usuário.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..logging_config import get_logger
from .store import AuditStore

logger = get_logger("api.retention")

# Só estes sufixos podem ser apagados (defesa contra um banco adulterado).
_REPORT_KEYS = ("report_md", "report_html", "report_sarif")
_REPORT_SUFFIXES = {".md", ".html", ".sarif"}


class AuditNotFoundError(LookupError):
    """A auditoria não existe."""


class AuditBusyError(RuntimeError):
    """A auditoria ainda está em execução neste processo."""


def delete_audit(audit_id: str, store: AuditStore, checkpointer: Any,
                 registry: dict[str, Any]) -> None:
    """Exclui a auditoria: relatórios → checkpoints → metadados → registry.

    A ordem garante que uma falha (ex.: permissão ao apagar um relatório) deixe o
    registro de metadados intacto, permitindo nova tentativa.

    Raises:
        AuditNotFoundError: id inexistente.
        AuditBusyError: há um runner vivo (não finalizado) para a auditoria.
        OSError: falha ao apagar um relatório (nada mais foi removido).
    """
    # A checagem de "viva" vem ANTES da leitura dos metadados: um runner que termina
    # no meio grava os caminhos dos relatórios; ler depois garante vê-los (senão os
    # relatórios — com trechos de código — ficariam órfãos no disco).
    runner = registry.get(audit_id)
    if runner is not None and not runner.done.is_set():
        raise AuditBusyError(audit_id)

    record = store.get(audit_id)
    if record is None:
        raise AuditNotFoundError(audit_id)

    for key in _REPORT_KEYS:
        path = record.get(key)
        if not path:
            continue
        target = Path(path)
        if target.suffix.lower() not in _REPORT_SUFFIXES:
            logger.warning("Relatório com sufixo inesperado não apagado: %s", target)
            continue
        target.unlink(missing_ok=True)

    checkpointer.delete_thread(audit_id)
    store.delete(audit_id)
    registry.pop(audit_id, None)
    logger.info("Auditoria %s excluída", audit_id)


@dataclass(frozen=True)
class CompactStats:
    """Resultado da compactação do banco de checkpoints."""

    removed_checkpoints: int
    removed_writes: int
    size_before: int
    size_after: int


def _db_size(db_path: Path) -> int:
    """Tamanho em disco do banco (arquivo principal + WAL)."""
    return sum(p.stat().st_size for p in (db_path, Path(f"{db_path}-wal")) if p.exists())


def compact_checkpoints(db_path: Path, timeout: float = 1.0) -> CompactStats:
    """Remove checkpoints/writes de sub-grafos (``checkpoint_ns != ''``) e faz VACUUM.

    Os checkpoints raiz (``checkpoint_ns == ''``) — de onde a API lê o estado das
    auditorias — são preservados. Exige acesso exclusivo: com a API rodando, o
    VACUUM falha com ``sqlite3.OperationalError`` ("database is locked").
    """
    size_before = _db_size(db_path)
    conn = sqlite3.connect(str(db_path), timeout=timeout)
    try:
        removed_cp = conn.execute("DELETE FROM checkpoints WHERE checkpoint_ns != ''").rowcount
        removed_wr = conn.execute("DELETE FROM writes WHERE checkpoint_ns != ''").rowcount
        conn.commit()
        conn.execute("VACUUM")
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()
    stats = CompactStats(removed_cp, removed_wr, size_before, _db_size(db_path))
    logger.info("Banco compactado: %s", stats)
    return stats
