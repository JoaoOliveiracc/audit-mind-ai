"""Utilitários de mensagens de LLM compartilhados pelos nós."""
from __future__ import annotations

from typing import Any


def content_text(content: Any) -> str:
    """Texto de ``AIMessage.content``: string, ou lista de blocos (Anthropic/Gemini)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            part.get("text", "") if isinstance(part, dict) else str(part) for part in content
        )
    return "" if content is None else str(content)
