"""Modelos de request/response da API."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


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
