"""Resumo executivo em texto puro (spec: .specs/features/investigator-budget — SYN-01..02)."""
from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage

from auditor.nodes import synthesis


class _LLM:
    def __init__(self, content):
        self._content = content

    def invoke(self, _messages):
        return AIMessage(content=self._content)


@pytest.mark.parametrize("content, expected", [
    ([{"type": "text", "text": "A"}, {"type": "text", "text": "B"}], "AB"),   # SYN-01
    ("Resumo em texto.", "Resumo em texto."),                                # SYN-02
])
def test_executive_summary_is_plain_text(monkeypatch, content, expected):
    monkeypatch.setattr(synthesis, "get_llm", lambda *a, **k: _LLM(content))
    out = synthesis.synthesis_node({"findings": [{"severity": "high"}]})
    assert out["executive_summary"] == expected
    assert out["health_score"] == 80
