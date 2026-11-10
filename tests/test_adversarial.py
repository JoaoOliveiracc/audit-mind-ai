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
    max_concurrent_investigators = 4


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


# --- G35: juiz em paralelo (search-and-judge-perf: ADV-01..03) ---------------------
import threading  # noqa: E402
import time  # noqa: E402

import pytest  # noqa: E402


class _SlowStructured:
    """Juiz falso: atrasa por achado (ordem de conclusão ≠ ordem de entrada) e mede concorrência."""

    def __init__(self, delays: dict[str, float]):
        self.delays = delays
        self.lock = threading.Lock()
        self.active = 0
        self.peak = 0

    def invoke(self, messages):
        text = messages[-1].content
        title = next(t for t in self.delays if t in text)
        with self.lock:
            self.active += 1
            self.peak = max(self.peak, self.active)
        try:
            time.sleep(self.delays[title])
            if "FALHAR" in title:
                raise RuntimeError("juiz indisponível")
            if "REFUTAR-ME" in title:
                return Verdict(verdict="refuted", rationale="r", confidence=0.9)
            if "CONFIRMAR-ME" in title:
                return Verdict(verdict="confirmed", rationale="c", confidence=0.9)
            return Verdict(verdict="uncertain", rationale="u", confidence=0.5)
        finally:
            with self.lock:
                self.active -= 1


def _run_parallel(tmp_path, monkeypatch, titles, delays, limit):
    root = _make_project(tmp_path)
    judge = _SlowStructured(dict(zip(titles, delays)))

    class _LLM:
        def with_structured_output(self, schema):
            return judge

    class _S(_Settings):
        max_concurrent_investigators = limit

    monkeypatch.setattr(adv, "get_settings", lambda: _S())
    monkeypatch.setattr(adv, "get_llm", lambda *a, **k: _LLM())
    findings = [{"dimension": "security", "title": t, "severity": "high", "description": "d",
                 "recommendation": "r", "file": "src/app.py", "line": 3, "confidence": 0.8}
                for t in titles]
    findings.insert(2, {"dimension": "quality", "title": "low-sev", "severity": "low",
                        "description": "d", "recommendation": "r", "file": "src/app.py"})
    out = adv.adversarial_node({"project_path": str(root), "findings": findings})
    return out, judge


TITLES = ["A CONFIRMAR-ME", "B REFUTAR-ME", "C neutro", "D REFUTAR-ME"]
DELAYS = [0.20, 0.05, 0.15, 0.01]       # termina em ordem D, B, C, A


def test_adv01_judges_concurrently_up_to_the_limit(tmp_path, monkeypatch):
    # Determinístico: cada julgamento espera os 4 numa barreira — só passa se rodarem juntos.
    barrier = threading.Barrier(4, timeout=5)
    real_invoke = _SlowStructured.invoke

    def invoke_with_barrier(self, messages):
        barrier.wait()
        return real_invoke(self, messages)

    monkeypatch.setattr(_SlowStructured, "invoke", invoke_with_barrier)
    out, _ = _run_parallel(tmp_path, monkeypatch, TITLES, [0.0] * 4, limit=4)
    # A barreira só libera com os 4 dentro dela ao mesmo tempo; se não estivessem juntos,
    # ela quebraria (timeout) e os vereditos sumiriam. Todos presentes ⇒ 4 simultâneos.
    stats = out["adversarial"]
    assert (stats["confirmed"], stats["refuted"], stats["uncertain"]) == (1, 2, 1)


def test_adv01_limit_one_is_sequential(tmp_path, monkeypatch):
    _, judge = _run_parallel(tmp_path, monkeypatch, TITLES, DELAYS, limit=1)
    assert judge.peak == 1


@pytest.mark.parametrize("limit", [1, 4])
def test_adv02_order_and_stats_match_sequential(tmp_path, monkeypatch, limit):
    out, _ = _run_parallel(tmp_path, monkeypatch, TITLES, DELAYS, limit=limit)

    assert [f["title"] for f in out["findings"]] == ["A CONFIRMAR-ME", "low-sev", "C neutro"]
    assert [f.get("judged") for f in out["findings"]] == ["confirmed", None, "uncertain"]
    stats = out["adversarial"]
    assert (stats["judged"], stats["confirmed"], stats["refuted"], stats["uncertain"]) == (4, 1, 2, 1)
    assert stats["refuted_titles"] == ["B REFUTAR-ME", "D REFUTAR-ME"]   # ordem de entrada


def test_adv03_one_failing_judge_is_isolated(tmp_path, monkeypatch):
    titles = ["A CONFIRMAR-ME", "B FALHAR", "C REFUTAR-ME"]
    out, _ = _run_parallel(tmp_path, monkeypatch, titles, [0.05, 0.01, 0.03], limit=4)

    assert [f["title"] for f in out["findings"]] == ["A CONFIRMAR-ME", "B FALHAR", "low-sev"]
    by_title = {f["title"]: f for f in out["findings"]}
    assert by_title["A CONFIRMAR-ME"]["judged"] == "confirmed"
    assert by_title["B FALHAR"].get("judged") is None                 # mantido, sem veredito
    assert out["adversarial"]["refuted_titles"] == ["C REFUTAR-ME"]



# --- ADV-03 com votes > 1 e ADV-04 (thread principal) ------------------------------------
from auditor.prompts.templates import JUDGE_LENSES  # noqa: E402


class _LensJudge:
    """Lente 0 falha; lente 1 confirma. Registra a lente de cada chamada e a thread do console."""

    def __init__(self):
        self.lenses: list[int] = []
        self.lock = threading.Lock()

    def invoke(self, messages):
        text = messages[-1].content
        lens = next(i for i, lens in enumerate(JUDGE_LENSES) if lens in text)
        with self.lock:
            self.lenses.append(lens)
        if lens == 0:
            raise RuntimeError("lente 0 indisponível")
        return Verdict(verdict="confirmed", rationale=f"lente {lens}", confidence=0.9)


def _run_votes(tmp_path, monkeypatch, console_threads, emit_threads):
    root = _make_project(tmp_path)
    judge = _LensJudge()

    class _LLM:
        def with_structured_output(self, schema):
            return judge

    class _S(_Settings):
        adversarial_votes = 2
        max_concurrent_investigators = 4

    class _Console:
        def print(self, *a, **k):
            console_threads.append(threading.current_thread().name)

    monkeypatch.setattr(adv, "get_settings", lambda: _S())
    monkeypatch.setattr(adv, "get_llm", lambda *a, **k: _LLM())
    monkeypatch.setattr(adv, "_console", _Console())
    monkeypatch.setattr(adv, "_emit", lambda data: emit_threads.append(threading.current_thread().name))
    findings = [{"dimension": "security", "title": t, "severity": "high", "description": "d",
                 "recommendation": "r", "file": "src/app.py", "line": 3, "confidence": 0.8}
                for t in ("F1", "F2")]
    return adv.adversarial_node({"project_path": str(root), "findings": findings}), judge


def test_adv03_failed_lens_does_not_stop_the_other_lenses(tmp_path, monkeypatch):
    out, judge = _run_votes(tmp_path, monkeypatch, [], [])

    assert sorted(judge.lenses) == [0, 0, 1, 1]          # cada achado: lente 0 (falha) + lente 1
    # agregação existente: maioria sobre os votos PEDIDOS (2) → 1 confirmação = incerto
    assert [f["judged"] for f in out["findings"]] == ["uncertain", "uncertain"]
    assert [f["judge_rationale"] for f in out["findings"]] == ["lente 1", "lente 1"]


def test_adv04_console_and_sse_only_from_main_thread(tmp_path, monkeypatch):
    console_threads: list[str] = []
    emit_threads: list[str] = []
    _run_votes(tmp_path, monkeypatch, console_threads, emit_threads)

    main = threading.main_thread().name
    assert len(console_threads) == 3                       # 2 avisos de lente + resumo final
    assert set(console_threads) == {main}
    assert emit_threads == [main]
