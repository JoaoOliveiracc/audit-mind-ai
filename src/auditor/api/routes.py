"""Endpoints da API do Audit Mind AI."""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse
from sse_starlette.sse import EventSourceResponse

from ..config import PROVIDER_ENV_VAR, PROVIDER_PACKAGE, get_settings
from ..llm import LLMConfigError, get_llm, reset_llm_cache
from .deps import get_graph, get_store, registry
from .runner import AuditRunner
from .schemas import (
    AnswersRequest,
    AuditSummary,
    BrowseEntry,
    BrowseResponse,
    CreateAuditRequest,
    ProviderInfo,
)

router = APIRouter()


@router.get("/providers", response_model=list[ProviderInfo])
def list_providers() -> list[ProviderInfo]:
    """Lista os provedores de LLM suportados."""
    return [
        ProviderInfo(provider=p, package=PROVIDER_PACKAGE[p],
                     credential_env=PROVIDER_ENV_VAR.get(p))
        for p in PROVIDER_PACKAGE
    ]


@router.get("/fs/browse", response_model=BrowseResponse)
def browse_fs(path: Optional[str] = None) -> BrowseResponse:
    """Lista subpastas de um diretório do host — alimenta o picker de projeto.

    Só lê nomes de diretórios (sem conteúdo de arquivo); a auditoria já exige
    o mesmo acesso de leitura ao filesystem, então isso não abre superfície
    nova — só torna o caminho navegável em vez de digitado à mão.
    """
    root = Path(path).expanduser().resolve() if path else Path.home()
    if not root.is_dir():
        raise HTTPException(400, f"Diretório não encontrado: {root}")

    entries: list[BrowseEntry] = []
    try:
        children = sorted(root.iterdir(), key=lambda p: p.name.lower())
    except PermissionError:
        children = []
    for child in children:
        if child.name.startswith("."):
            continue
        try:
            if child.is_dir():
                entries.append(BrowseEntry(name=child.name, path=str(child)))
        except PermissionError:
            continue

    parent = str(root.parent) if root.parent != root else None
    return BrowseResponse(path=str(root), parent=parent, entries=entries)


@router.post("/audits", response_model=AuditSummary, status_code=201)
def create_audit(req: CreateAuditRequest) -> AuditSummary:
    """Cria e inicia uma auditoria em background."""
    root = Path(req.project_path).expanduser()
    if not root.is_dir():
        raise HTTPException(400, f"Caminho de projeto inválido: {req.project_path}")

    # Override de provedor/modelo (processo-global; para uso local single-user).
    if req.provider:
        os.environ["AUDITOR_PROVIDER"] = req.provider
    if req.model:
        os.environ["AUDITOR_MODEL"] = req.model
    if req.provider or req.model:
        get_settings.cache_clear()
        reset_llm_cache()

    try:  # valida credencial/pacote do provedor cedo
        get_llm()
    except LLMConfigError as exc:
        raise HTTPException(400, str(exc)) from exc

    settings = get_settings()
    audit_id = uuid.uuid4().hex
    initial = {
        "project_path": str(root.resolve()),
        "user_goal": req.goal or "",
        "skip_questions": not req.interactive,
        "user_context": {},
        "findings": [],
        "dimension_summaries": [],
        "status": "started",
    }

    store = get_store()
    store.create(audit_id, str(root.resolve()), req.goal, settings.provider, settings.model)

    runner = AuditRunner(audit_id, get_graph(), store, initial)
    registry[audit_id] = runner
    runner.start()

    return _summary(store.get(audit_id))


@router.get("/audits", response_model=list[AuditSummary])
def list_audits() -> list[AuditSummary]:
    """Lista as auditorias (histórico local)."""
    return [_summary(r) for r in get_store().list()]


@router.get("/audits/{audit_id}", response_model=AuditSummary)
def get_audit(audit_id: str) -> AuditSummary:
    """Retorna o estado atual de uma auditoria."""
    record = get_store().get(audit_id)
    if not record:
        raise HTTPException(404, "Auditoria não encontrada.")
    return _summary(record)


@router.get("/audits/{audit_id}/stream")
async def stream_audit(audit_id: str):
    """SSE: progresso, esclarecimentos e conclusão da auditoria."""
    runner = registry.get(audit_id)
    if runner is None:
        raise HTTPException(404, "Auditoria não encontrada ou já finalizada nesta instância.")

    async def event_source():
        idx = 0
        while True:
            while idx < len(runner.log):
                ev = runner.log[idx]
                idx += 1
                if ev["event"] == "__end__":
                    return
                yield {"event": ev["event"],
                       "data": json.dumps(ev["data"], ensure_ascii=False)}
            if runner.done.is_set() and idx >= len(runner.log):
                return
            await asyncio.sleep(0.15)

    return EventSourceResponse(event_source())


@router.post("/audits/{audit_id}/answers")
def submit_answers(audit_id: str, req: AnswersRequest) -> dict:
    """Envia respostas de esclarecimento e retoma a auditoria."""
    runner = registry.get(audit_id)
    if runner is None:
        raise HTTPException(404, "Auditoria não encontrada nesta instância.")
    runner.submit_answers(req.answers)
    return {"status": "resumed"}


@router.get("/audits/{audit_id}/findings")
def get_findings(audit_id: str) -> dict:
    """Achados estruturados para o dashboard."""
    if not get_store().get(audit_id):
        raise HTTPException(404, "Auditoria não encontrada.")
    config = {"configurable": {"thread_id": audit_id}}
    values = get_graph().get_state(config).values
    return {
        "findings": values.get("findings", []),
        "dimension_summaries": values.get("dimension_summaries", []),
        "health_score": values.get("health_score"),
        "executive_summary": values.get("executive_summary", ""),
        "stack_profile": values.get("stack_profile", {}),
        "verification": values.get("verification", {}),
        "adversarial": values.get("adversarial", {}),
    }


@router.get("/audits/{audit_id}/report")
def get_report(audit_id: str, format: str = "html"):
    """Retorna o relatório renderizado (html | md)."""
    record = get_store().get(audit_id)
    if not record:
        raise HTTPException(404, "Auditoria não encontrada.")
    key = "report_html" if format == "html" else "report_md"
    path = record.get(key)
    if not path or not Path(path).is_file():
        raise HTTPException(409, "Relatório ainda não disponível.")
    content = Path(path).read_text(encoding="utf-8")
    if format == "html":
        return HTMLResponse(content)
    return PlainTextResponse(content)


def _summary(record: dict) -> AuditSummary:
    return AuditSummary(
        id=record["id"], status=record["status"], project_path=record["project_path"],
        goal=record.get("goal"), provider=record.get("provider"), model=record.get("model"),
        created_at=record["created_at"], health_score=record.get("health_score"),
        counts=record.get("counts"), error=record.get("error"),
    )
