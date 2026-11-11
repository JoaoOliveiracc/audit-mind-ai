"""Chat sobre o relatório de uma auditoria concluída (G42).

Funções puras: montam a entrada do LLM a partir do estado final do grafo. O conteúdo do
relatório vem do código auditado, então vai delimitado e marcado como dado não confiável.
"""
from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from .prompts.templates import CHAT_SYSTEM
from .scoring import dependency_penalty_line
from .state import Severity

__all__ = ["CHAT_SYSTEM", "build_chat_messages", "build_report_context"]

_EVIDENCE_CHARS = 500
_CONTEXT_CHARS = 30_000
_RANK = {s.value: i for i, s in enumerate(Severity)}


# Qualquer caixa e espaços internos: `</RELATORIO>`, `< /relatorio >`… (não podem fechar o bloco).
_TAG = re.compile(r"<\s*(/?)\s*relatorio\s*>", re.IGNORECASE)


def _neutralize(text: str) -> str:
    return _TAG.sub(lambda m: f"‹{m.group(1)}relatorio›", text)


def build_report_context(values: dict[str, Any]) -> str:
    """Texto do relatório (sem delimitadores), com teto de tamanho; achados mais graves primeiro."""
    lines = [f"Pontuação de saúde: {values.get('health_score', '—')}/100"]
    explanation = dependency_penalty_line(values.get("dependency_penalty"))
    if explanation:
        lines.append(explanation)
    lines += [
        "Resumo executivo:",
        str(values.get("executive_summary") or "(não gerado)"),
        f"Perfil técnico: {json.dumps(values.get('stack_profile') or {}, ensure_ascii=False)}",
        "Resumo por dimensão:",
        *[f"- {d.get('dimension', '?')}: {d.get('summary', '')}"
          for d in values.get("dimension_summaries") or []],
        "Achados:",
    ]
    findings = sorted(values.get("findings") or [],
                      key=lambda f: _RANK.get(f.get("severity", "info"), len(_RANK)))
    if not findings:
        lines.append("Nenhum achado registrado.")
    for i, f in enumerate(findings, start=1):
        location = f.get("file") or "—"
        if f.get("line"):
            location += f":{f['line']}"
        lines.append(f"{i}. [{f.get('severity', 'info')}] {f.get('title', '(sem título)')} "
                     f"({f.get('dimension', '?')}) — {location}")
        lines.append(f"   Descrição: {f.get('description', '')}")
        lines.append(f"   Recomendação: {f.get('recommendation', '')}")
        if f.get("evidence"):
            lines.append(f"   Evidência: {str(f['evidence'])[:_EVIDENCE_CHARS]}")
    context = _neutralize("\n".join(lines))
    return context[:_CONTEXT_CHARS]


def build_chat_messages(values: dict[str, Any], history: list[dict[str, str]],
                        question: str) -> list[BaseMessage]:
    """System → relatório delimitado → histórico (em ordem) → pergunta."""
    messages: list[BaseMessage] = [
        SystemMessage(content=CHAT_SYSTEM),
        HumanMessage(content=f"<relatorio>\n{build_report_context(values)}\n</relatorio>"),
    ]
    for turn in history:
        cls = AIMessage if turn["role"] == "assistant" else HumanMessage
        messages.append(cls(content=turn["content"]))
    messages.append(HumanMessage(content=question))
    return messages
