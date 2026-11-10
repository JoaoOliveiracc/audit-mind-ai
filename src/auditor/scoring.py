"""Pontuação de saúde e contagem por severidade — fonte única (G41)."""
from __future__ import annotations

from .state import SEVERITY_WEIGHT, Severity


def compute_health_score(findings: list[dict]) -> int:
    """Calcula uma pontuação de 0 a 100 a partir da severidade dos achados."""
    penalty = sum(SEVERITY_WEIGHT.get(f.get("severity", "info"), 0) for f in findings)
    return max(0, 100 - min(100, penalty))


def severity_counts(findings: list[dict], include_zero: bool = True) -> dict[str, int]:
    """Conta achados por severidade (ausente = ``info``).

    ``include_zero=True``: as 5 severidades, em ordem (critical → info), mesmo com 0 —
    relatório, síntese e CLI. ``include_zero=False``: só as presentes — ``counts`` da API.
    """
    counts: dict[str, int] = {s.value: 0 for s in Severity} if include_zero else {}
    for f in findings:
        sev = f.get("severity") or Severity.INFO.value
        counts[sev] = counts.get(sev, 0) + 1
    return counts
