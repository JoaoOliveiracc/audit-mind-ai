"""Eventos de progresso e rótulos dos nós — fonte única para nós, API e CLI (G41)."""
from __future__ import annotations

from typing import Any, Callable, Optional

# Disponível apenas em versões recentes do LangGraph; Optional para o mypy.
get_stream_writer: Optional[Callable[[], Callable[[Any], None]]]
try:
    from langgraph.config import get_stream_writer
except ImportError:  # pragma: no cover
    get_stream_writer = None

# Rótulo de cada nó do grafo (eventos `phase` da API e linhas da CLI).
NODE_LABELS: dict[str, str] = {
    "discovery": "Descoberta e detecção de stack",
    "plan_questions": "Gerando perguntas de esclarecimento",
    "clarify": "Esclarecimentos",
    "planning": "Planejando dimensões",
    "audit": "Executando investigadores",
    "dependency_scan": "Verificando dependências vulneráveis",
    "verify": "Verificando evidência dos achados",
    "adversarial": "Julgamento adversarial dos achados",
    "synthesis": "Consolidando e pontuando",
    "report": "Gerando relatório",
}

# Ícones da CLI (mesmas chaves de NODE_LABELS).
NODE_ICONS: dict[str, str] = {
    "discovery": "🔎", "plan_questions": "❓", "clarify": "💬", "planning": "🗺️ ",
    "audit": "🕵️ ", "dependency_scan": "📦", "verify": "🔬", "adversarial": "⚖️ ", "synthesis": "🧠", "report": "📄",
}


def emit(data: dict) -> None:
    """Emite um evento no stream 'custom' do LangGraph (para a API/SSE).

    No-op seguro: fora de um run com ``stream_mode='custom'`` (ex.: CLI, testes) ou numa
    thread sem o contexto do LangGraph, a escrita é simplesmente descartada.
    """
    if get_stream_writer is None:
        return
    try:
        get_stream_writer()(data)
    except Exception:
        pass
