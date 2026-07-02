"""Singletons compartilhados da API (inicializados sob demanda)."""
from __future__ import annotations

from functools import lru_cache

from ..graph import build_graph
from .runner import AuditRunner
from .store import AuditStore, build_checkpointer


@lru_cache
def get_graph():
    """Grafo compilado com checkpointer SQLite persistente (singleton)."""
    return build_graph(checkpointer=build_checkpointer())


@lru_cache
def get_store() -> AuditStore:
    """Store de metadados (singleton)."""
    return AuditStore()


# Registro em memória das auditorias em execução nesta instância do processo.
registry: dict[str, AuditRunner] = {}
