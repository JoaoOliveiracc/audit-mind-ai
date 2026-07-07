"""Execução de auditorias em background com streaming de eventos e human-in-the-loop.

Cada auditoria roda em uma thread própria (o grafo faz I/O de rede bloqueante).
Os eventos são acumulados em ``log`` (lista) — o endpoint SSE lê por índice, o que
dá replay e suporte a reconexão de graça.
"""
from __future__ import annotations

import threading
from typing import Any, Optional

from langgraph.types import Command

from ..logging_config import get_logger
from .store import AuditStore

logger = get_logger("api.runner")

NODE_LABELS = {
    "discovery": "Descoberta e detecção de stack",
    "plan_questions": "Gerando perguntas de esclarecimento",
    "clarify": "Esclarecimentos",
    "planning": "Planejando dimensões",
    "audit": "Executando investigadores",
    "verify": "Verificando evidência dos achados",
    "adversarial": "Julgamento adversarial dos achados",
    "synthesis": "Consolidando e pontuando",
    "report": "Gerando relatório",
}


def _counts(findings: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for f in findings:
        sev = f.get("severity", "info")
        counts[sev] = counts.get(sev, 0) + 1
    return counts


class AuditRunner:
    """Roda uma auditoria e publica eventos consumíveis via SSE."""

    def __init__(self, audit_id: str, graph, store: AuditStore, initial: dict) -> None:
        self.id = audit_id
        self._graph = graph
        self._store = store
        self._initial = initial
        self._config = {"configurable": {"thread_id": audit_id}}
        self.log: list[dict] = []
        self.done = threading.Event()
        self._resume_answers: Optional[dict] = None
        self._resume_ready = threading.Event()
        self._thread = threading.Thread(target=self._run, name=f"audit-{audit_id}", daemon=True)

    # -- API pública ------------------------------------------------------- #
    def start(self) -> None:
        self._thread.start()

    def submit_answers(self, answers: dict) -> None:
        self._resume_answers = answers or {}
        self._resume_ready.set()

    @property
    def waiting_for_input(self) -> bool:
        return not self._resume_ready.is_set() and not self.done.is_set() \
            and any(e["event"] == "clarification" for e in self.log)

    # -- Interno ----------------------------------------------------------- #
    def _emit(self, event: str, data: dict) -> None:
        self.log.append({"event": event, "data": data})

    def _drive(self, graph_input: Any) -> str:
        """Consome o stream do grafo até concluir ou pausar. Retorna 'done'|'interrupted'."""
        for mode, payload in self._graph.stream(
            graph_input, self._config, stream_mode=["updates", "custom"]
        ):
            if mode == "custom":
                self._emit(payload.get("type", "progress"), payload)
                continue
            # mode == "updates"
            if "__interrupt__" in payload:
                intr = payload["__interrupt__"][0]
                value = getattr(intr, "value", {}) or {}
                self._emit("clarification", {"questions": value.get("questions", [])})
                return "interrupted"
            for node in payload:
                self._emit("phase", {"node": node,
                                     "label": NODE_LABELS.get(node, node), "status": "done"})
        return "done"

    def _run(self) -> None:
        logger.info("Auditoria %s iniciada", self.id)
        try:
            result = self._drive(self._initial)
            while result == "interrupted":
                self._store.update(self.id, status="waiting_input")
                self._resume_ready.wait()
                self._resume_ready.clear()
                self._store.update(self.id, status="running")
                result = self._drive(Command(resume=self._resume_answers or {}))

            final = self._graph.get_state(self._config).values
            health = final.get("health_score")
            counts = _counts(final.get("findings", []))
            self._store.update(
                self.id, status="completed", health_score=health, counts=counts,
                report_html=final.get("report_html_path"),
                report_md=final.get("report_markdown_path"),
            )
            self._emit("completed", {"health_score": health, "counts": counts})
            logger.info("Auditoria %s concluída (score=%s)", self.id, health)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Auditoria %s falhou: %s", self.id, exc)
            self._store.update(self.id, status="error", error=str(exc))
            self._emit("error", {"message": str(exc)})
        finally:
            self.done.set()
            self._emit("__end__", {})
