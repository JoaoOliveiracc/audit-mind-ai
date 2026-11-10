"""Modelos de request/response da API."""
from __future__ import annotations

from typing import Annotated, Literal, Optional

from pydantic import BaseModel, Field, StringConstraints


class CreateAuditRequest(BaseModel):
    """Corpo para iniciar uma auditoria."""

    project_path: str = Field(description="Caminho absoluto do projeto a auditar.")
    goal: Optional[str] = Field(default=None, description="Objetivo/contexto da auditoria.")
    provider: Optional[str] = Field(default=None, description="Provedor de LLM (sobrescreve o .env).")
    model: Optional[str] = Field(default=None, description="Modelo (sobrescreve o .env).")
    interactive: bool = Field(default=True, description="Se False, pula a fase de esclarecimentos.")


class AnswersRequest(BaseModel):
    """Respostas de esclarecimento para retomar uma auditoria pausada."""

    answers: dict[str, str] = Field(default_factory=dict)


class AuditSummary(BaseModel):
    """Resumo do estado de uma auditoria."""

    id: str
    status: str
    project_path: str
    goal: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    created_at: str
    health_score: Optional[int] = None
    counts: Optional[dict[str, int]] = None
    error: Optional[str] = None


class ProviderInfo(BaseModel):
    """Descrição de um provedor de LLM suportado."""

    provider: str
    package: str
    credential_env: Optional[str] = None


class BrowseEntry(BaseModel):
    """Uma subpasta listável no picker de diretório."""

    name: str
    path: str


class BrowseResponse(BaseModel):
    """Listagem de um diretório do host, para o picker de caminho do projeto."""

    path: str
    parent: Optional[str] = None
    entries: list[BrowseEntry]


class ChatTurn(BaseModel):
    """Uma troca anterior da conversa (só na tela do usuário; reenviada a cada pergunta)."""

    role: Literal["user", "assistant"]
    content: Annotated[str, StringConstraints(max_length=4_000)]


class ChatRequest(BaseModel):
    """Pergunta sobre o relatório + até 10 trocas anteriores."""

    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2_000)]
    history: list[ChatTurn] = Field(default_factory=list, max_length=10)


class ChatResponse(BaseModel):
    answer: str
