"""Endpoints da API do Audit Mind AI."""
from __future__ import annotations

import asyncio
import json
import threading
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from sse_starlette.sse import EventSourceResponse

from ..chat import build_chat_messages
from ..config import PROVIDER_ENV_VAR, PROVIDER_PACKAGE, get_settings
from ..llm import LLMConfigError, get_llm
from ..nodes._messages import content_text
from .deps import get_checkpointer, get_graph, get_store, registry
from .retention import AuditBusyError, AuditNotFoundError, delete_audit
from .runner import AuditRunner
from .schemas import (
    AnswersRequest,
    AuditSummary,
    BrowseEntry,
    BrowseResponse,
    ChatRequest,
    ChatResponse,
    CreateAuditRequest,
    ProviderInfo,
)

router = APIRouter()

# Serializa transições de ciclo de vida (resume × resume, resume × delete): checar
# status/registry e registrar o runner precisa ser atômico neste processo.
_lifecycle_lock = threading.Lock()


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

    # Provedor/modelo efetivos: override do request ou default das settings.
    # Passados via estado do grafo (sem mutar os.environ global) — auditorias
    # concorrentes podem usar provedores distintos com segurança.
    settings = get_settings()
    provider = req.provider or settings.provider
    model = req.model or settings.model

    try:  # valida credencial/pacote do provedor cedo
        get_llm(provider, model)
    except LLMConfigError as exc:
        raise HTTPException(400, str(exc)) from exc

    audit_id = uuid.uuid4().hex
    initial = {
        "project_path": str(root.resolve()),
        "user_goal": req.goal or "",
        "provider": provider,
        "model": model,
        "skip_questions": not req.interactive,
        "vuln_scan": settings.vuln_scan if req.vuln_scan is None else req.vuln_scan,
        "user_context": {},
        "findings": [],
        "dimension_summaries": [],
        "status": "started",
    }

    store = get_store()
    store.create(audit_id, str(root.resolve()), req.goal, provider, model)

    runner = AuditRunner(audit_id, get_graph(), store, initial)
    registry[audit_id] = runner
    runner.start()

    return _summary(_require(store, audit_id))


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


@router.post("/audits/{audit_id}/chat", response_model=ChatResponse)
def chat_with_report(audit_id: str, req: ChatRequest) -> ChatResponse:
    """Responde perguntas sobre o relatório de uma auditoria concluída (sem ler código)."""
    record = get_store().get(audit_id)
    if not record:
        raise HTTPException(404, "Auditoria não encontrada.")
    if record["status"] != "completed":
        raise HTTPException(409, "Chat disponível só para auditorias concluídas.")
    values = get_graph().get_state({"configurable": {"thread_id": audit_id}}).values
    if not values:
        raise HTTPException(409, "Estado da auditoria indisponível para o chat.")
    try:
        llm = get_llm(record.get("provider"), record.get("model"))
    except LLMConfigError as exc:
        raise HTTPException(400, str(exc)) from exc

    messages = build_chat_messages(values, [t.model_dump() for t in req.history], req.question)
    try:
        response = llm.invoke(messages)
    except Exception as exc:  # erro do provedor (rate limit, rede…)
        raise HTTPException(502, f"Falha ao consultar o LLM: {exc}") from exc
    answer = content_text(response.content).strip()
    if not answer:
        raise HTTPException(502, "O LLM devolveu uma resposta vazia.")
    return ChatResponse(answer=answer)


@router.post("/audits/{audit_id}/resume", response_model=AuditSummary)
def resume_audit(audit_id: str) -> AuditSummary:
    """Retoma uma auditoria ``interrupted`` (órfã após restart) do último checkpoint."""
    store = get_store()
    record = store.get(audit_id)
    if not record:
        raise HTTPException(404, "Auditoria não encontrada.")
    runner = registry.get(audit_id)
    if runner is not None and not runner.done.is_set():
        raise HTTPException(409, "Auditoria já está em execução.")
    if record["status"] != "interrupted":
        raise HTTPException(409, "Só auditorias interrompidas podem ser retomadas.")

    try:  # valida credencial/pacote do provedor da auditoria antes de retomar
        get_llm(record.get("provider"), record.get("model"))
    except LLMConfigError as exc:
        raise HTTPException(400, str(exc)) from exc

    # A validação (lenta) acontece fora do lock; dentro dele, rechecamos o estado —
    # outra requisição pode ter retomado ou excluído a auditoria nesse meio-tempo.
    with _lifecycle_lock:
        record = store.get(audit_id)
        if not record:
            raise HTTPException(404, "Auditoria não encontrada.")
        live = registry.get(audit_id)
        if live is not None and not live.done.is_set():
            raise HTTPException(409, "Auditoria já está em execução.")
        if record["status"] != "interrupted":
            raise HTTPException(409, "Só auditorias interrompidas podem ser retomadas.")
        store.update(audit_id, status="running")
        runner = AuditRunner(audit_id, get_graph(), store, None, resume=True)
        registry[audit_id] = runner
    runner.start()
    return _summary(_require(store, audit_id))


@router.delete("/audits/{audit_id}", status_code=204)
def remove_audit(audit_id: str) -> Response:
    """Exclui a auditoria: metadados, checkpoints e relatórios (.md/.html/.sarif)."""
    try:
        with _lifecycle_lock:
            delete_audit(audit_id, get_store(), get_checkpointer(), registry)
    except AuditNotFoundError:
        raise HTTPException(404, "Auditoria não encontrada.")
    except AuditBusyError:
        raise HTTPException(409, "Auditoria em execução; aguarde a conclusão para excluir.")
    except OSError as exc:
        raise HTTPException(500, f"Falha ao apagar arquivos da auditoria: {exc}") from exc
    return Response(status_code=204)


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
        "dependency_scan": values.get("dependency_scan", {}),
    }


@router.get("/audits/{audit_id}/report")
def get_report(audit_id: str, format: str = "html"):
    """Retorna o relatório renderizado (html | md | sarif)."""
    record = get_store().get(audit_id)
    if not record:
        raise HTTPException(404, "Auditoria não encontrada.")
    key = {"html": "report_html", "md": "report_md", "sarif": "report_sarif"}.get(
        format, "report_html"
    )
    path = record.get(key)
    if not path or not Path(path).is_file():
        raise HTTPException(409, "Relatório ainda não disponível.")
    content = Path(path).read_text(encoding="utf-8")
    if format == "html":
        return HTMLResponse(content)
    if format == "sarif":
        return Response(content, media_type="application/sarif+json")
    return PlainTextResponse(content)


def _require(store, audit_id: str) -> dict:
    """Registro que acabou de ser criado/atualizado; ausência indica estado inconsistente."""
    record = store.get(audit_id)
    if record is None:
        raise HTTPException(500, "Estado inconsistente: auditoria não encontrada após gravação.")
    return record


def _summary(record: dict) -> AuditSummary:
    return AuditSummary(
        id=record["id"], status=record["status"], project_path=record["project_path"],
        goal=record.get("goal"), provider=record.get("provider"), model=record.get("model"),
        created_at=record["created_at"], health_score=record.get("health_score"),
        counts=record.get("counts"), error=record.get("error"),
    )
