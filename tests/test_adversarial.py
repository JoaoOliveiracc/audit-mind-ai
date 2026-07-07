"""Testes do nó de verificação adversarial (LLM falso, sem tokens)."""
from __future__ import annotations

from pathlib import Path

import auditor.nodes.adversarial as adv
from auditor.state import Verdict


class _FakeStructured:
    """Decide o veredito a partir de um marcador no título embutido no prompt."""

    def invoke(self, messages):
        text = messages[-1].content
        if "REFUTAR-ME" in text:
            return Verdict(verdict="refuted", rationale="não sustentado", confidence=0.9)
        if "CONFIRMAR-ME" in text:
            return Verdict(verdict="confirmed", rationale="sustentado", confidence=0.9)
        return Verdict(verdict="uncertain", rationale="ambíguo", confidence=0.5)


class _FakeLLM:
    def with_structured_output(self, schema):
        return _FakeStructured()


class _Settings:
    verify_adversarial = True
    adversarial_min_severity = "high"
    adversarial_votes = 1
    max_file_bytes = 200_000


def _make_project(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("x = 1\n" * 20, encoding="utf-8")
    return tmp_path


def test_adversarial_drops_refuted_keeps_confirmed(tmp_path, monkeypatch):
    root = _make_project(tmp_path)
    monkeypatch.setattr(adv, "get_settings", lambda: _Settings())
    monkeypatch.setattr(adv, "get_llm", lambda *a, **k: _FakeLLM())

    findings = [
        {"title": "REFUTAR-ME falso positivo", "severity": "critical",
         "file": "src/app.py", "line": 3, "evidence": "x = 1", "confidence": 0.9},
        {"title": "CONFIRMAR-ME vuln real", "severity": "high",
         "file": "src/app.py", "line": 5, "evidence": "x = 1", "confidence": 0.9},
        {"title": "achado ambíguo", "severity": "high",
         "file": "src/app.py", "line": 7, "evidence": "x = 1", "confidence": 0.9},
        {"title": "achado menor", "severity": "low",
         "file": "src/app.py", "line": 9, "evidence": "x = 1", "confidence": 0.6},
        {"title": "achado arquitetural", "severity": "critical",
         "file": None, "evidence": None, "confidence": 0.8},
    ]
    out = adv.adversarial_node({"project_path": str(root), "findings": findings})

    kept = {f["title"] for f in out["findings"]}
    stats = out["adversarial"]

    assert "REFUTAR-ME falso positivo" not in kept  # refutado -> descartado
    assert kept == {"CONFIRMAR-ME vuln real", "achado ambíguo", "achado menor", "achado arquitetural"}
    assert stats["judged"] == 3          # só critical/high COM arquivo
    assert stats["confirmed"] == 1
    assert stats["refuted"] == 1
    assert stats["uncertain"] == 1

    confirmed = next(f for f in out["findings"] if f["title"] == "CONFIRMAR-ME vuln real")
    assert confirmed["judged"] == "confirmed"
    uncertain = next(f for f in out["findings"] if f["title"] == "achado ambíguo")
    assert uncertain["judged"] == "uncertain" and uncertain["confidence"] <= 0.5


def test_adversarial_disabled_is_passthrough(tmp_path, monkeypatch):
    class _Off(_Settings):
        verify_adversarial = False
    monkeypatch.setattr(adv, "get_settings", lambda: _Off())
    findings = [{"title": "x", "severity": "critical", "file": "a.py"}]
    out = adv.adversarial_node({"project_path": str(tmp_path), "findings": findings})
    assert out["adversarial"]["enabled"] is False
    assert "findings" not in out  # passthrough: não reescreve
