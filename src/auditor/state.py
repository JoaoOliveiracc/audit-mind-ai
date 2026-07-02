"""Modelos de dados e estado do grafo do agent."""
from __future__ import annotations

import operator
from enum import Enum
from typing import Annotated, Any, Optional, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
# Enums                                                                        #
# --------------------------------------------------------------------------- #
class Severity(str, Enum):
    """Severidade de um achado de auditoria."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


# Peso usado para pontuação de saúde do projeto.
SEVERITY_WEIGHT: dict[str, int] = {
    Severity.CRITICAL.value: 40,
    Severity.HIGH.value: 20,
    Severity.MEDIUM.value: 8,
    Severity.LOW.value: 3,
    Severity.INFO.value: 0,
}


class AuditDimension(str, Enum):
    """Dimensões de auditoria suportadas (agnósticas de stack)."""

    SECURITY = "security"
    QUALITY = "quality"
    ARCHITECTURE = "architecture"
    DEPENDENCIES = "dependencies"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    PERFORMANCE = "performance"
    CICD = "cicd"
    OBSERVABILITY = "observability"
    COMPLIANCE = "compliance"


# --------------------------------------------------------------------------- #
# Modelos de domínio                                                           #
# --------------------------------------------------------------------------- #
class Finding(BaseModel):
    """Um único achado de auditoria."""

    dimension: str = Field(description="Dimensão de auditoria (ex.: security, quality).")
    title: str = Field(description="Título curto e objetivo do achado.")
    severity: Severity = Field(description="Severidade do achado.")
    description: str = Field(description="Explicação clara do problema e seu impacto.")
    recommendation: str = Field(description="Ação concreta e acionável para corrigir.")
    file: Optional[str] = Field(default=None, description="Arquivo relacionado (relativo à raiz).")
    line: Optional[int] = Field(default=None, description="Linha aproximada, se aplicável.")
    evidence: Optional[str] = Field(default=None, description="Trecho de código ou evidência.")
    confidence: float = Field(default=0.7, ge=0.0, le=1.0, description="Confiança de 0 a 1.")
    verified: Optional[bool] = Field(
        default=None,
        description="Preenchido pelo nó de verificação: True se a evidência foi localizada no arquivo.",
    )
    judged: Optional[str] = Field(
        default=None,
        description="Preenchido pelo juiz adversarial: 'confirmed' ou 'uncertain'.",
    )


class DimensionResult(BaseModel):
    """Resultado estruturado de um investigador de uma dimensão."""

    dimension: str = Field(description="Dimensão auditada.")
    summary: str = Field(description="Resumo executivo dos achados desta dimensão.")
    findings: list[Finding] = Field(default_factory=list, description="Lista de achados.")


class Verdict(BaseModel):
    """Veredito do juiz adversarial sobre um achado."""

    verdict: str = Field(description="Um de: confirmed, refuted, uncertain.")
    rationale: str = Field(description="Justificativa curta e objetiva do veredito.")
    confidence: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Confiança do juiz de 0 a 1."
    )


class ClarifyingQuestion(BaseModel):
    """Pergunta de esclarecimento ao usuário."""

    question: str = Field(description="Pergunta a ser feita ao usuário.")
    rationale: str = Field(description="Por que esta resposta melhora a auditoria.")


class ClarifyingQuestions(BaseModel):
    """Conjunto de perguntas geradas pelo agent."""

    questions: list[ClarifyingQuestion] = Field(default_factory=list)


class StackProfile(BaseModel):
    """Perfil técnico detectado do projeto."""

    languages: dict[str, int] = Field(default_factory=dict, description="Linguagem -> nº de arquivos.")
    frameworks: list[str] = Field(default_factory=list)
    package_managers: list[str] = Field(default_factory=list)
    marker_files: list[str] = Field(default_factory=list, description="Arquivos-marcadores encontrados.")
    has_tests: bool = False
    has_ci: bool = False
    has_docker: bool = False
    has_git: bool = False
    total_files: int = 0
    total_loc: int = 0


class AuditPlan(BaseModel):
    """Plano de auditoria: dimensões a executar e foco."""

    dimensions: list[str] = Field(default_factory=list)
    focus_notes: str = Field(default="", description="Notas de foco derivadas do contexto do usuário.")


# --------------------------------------------------------------------------- #
# Estado do grafo (LangGraph)                                                  #
# --------------------------------------------------------------------------- #
class AuditState(TypedDict, total=False):
    """Estado compartilhado entre os nós do grafo.

    ``findings`` usa o reducer ``operator.add`` para acumular achados de
    múltiplos investigadores; ``messages`` usa ``add_messages`` para o histórico.
    """

    # Entradas
    project_path: str
    user_goal: str

    # Conversa
    messages: Annotated[list[AnyMessage], add_messages]

    # Descoberta
    stack_profile: dict[str, Any]
    inventory: str  # árvore resumida + metadados textuais

    # Esclarecimento
    skip_questions: bool
    clarifying_questions: list[dict[str, Any]]
    user_context: dict[str, str]

    # Planejamento
    plan: dict[str, Any]

    # Auditoria
    # ``findings`` NÃO usa reducer aditivo: o nó ``audit`` o preenche e o nó
    # ``verify`` o reescreve com a lista filtrada (evidência confirmada).
    findings: list[dict[str, Any]]
    dimension_summaries: Annotated[list[dict[str, Any]], operator.add]

    # Verificação de evidência (estatísticas do nó verify)
    verification: dict[str, Any]
    # Verificação adversarial (estatísticas do juiz LLM)
    adversarial: dict[str, Any]

    # Síntese / relatório
    health_score: int
    executive_summary: str
    report_markdown_path: str
    report_html_path: str

    # Controle
    status: str
