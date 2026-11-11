"""Pontuação de saúde e contagem por severidade — fonte única (G41).

G49: os achados de pacotes vulneráveis (``source == "osv"``, definido só pelo scanner) tiram,
em grupo, no máximo ``DEPENDENCY_PENALTY_CAP`` pontos; os demais (LLM, runtimes) pesam inteiros.
"""
from __future__ import annotations

from typing import Any, Mapping, NamedTuple

from .state import SEVERITY_WEIGHT, Severity
from .vulnscan.models import OSV_SOURCE

# Fixo e independente de SEVERITY_WEIGHT: mudar pesos não pode mover o teto sem querer.
DEPENDENCY_PENALTY_CAP = 40


class DependencyPenalty(NamedTuple):
    applied: int     # o que de fato sai da nota (com teto)
    uncapped: int    # soma dos pesos sem teto
    packages: int    # achados OSV com peso > 0 — o scanner gera um por (ecossistema, nome, versão)


def _weight(finding: Mapping[str, Any]) -> int:
    return SEVERITY_WEIGHT.get(finding.get("severity") or "info", 0)


def dependency_penalty(findings: list[dict]) -> DependencyPenalty:
    """Penalidade do grupo de pacotes vulneráveis (OSV), com e sem o teto."""
    weights = [w for f in findings if f.get("source") == OSV_SOURCE and (w := _weight(f)) > 0]
    uncapped = sum(weights)
    return DependencyPenalty(min(DEPENDENCY_PENALTY_CAP, uncapped), uncapped, len(weights))


def score_with_breakdown(findings: list[dict]) -> tuple[int, DependencyPenalty]:
    """Nota e detalhamento do grupo OSV numa única passada — o que se grava é o que se subtraiu."""
    dp = dependency_penalty(findings)
    others = sum(_weight(f) for f in findings if f.get("source") != OSV_SOURCE)
    return max(0, 100 - min(100, others + dp.applied)), dp


def compute_health_score(findings: list[dict]) -> int:
    """Calcula uma pontuação de 0 a 100 a partir da severidade dos achados."""
    return score_with_breakdown(findings)[0]


def dependency_penalty_line(stored: Mapping[str, Any] | None) -> str | None:
    """Linha de explicação a partir do detalhamento GRAVADO no estado (nunca recalculado).

    ``None`` sem penalidade ou sem detalhamento (auditoria anterior à G49).
    """
    if not stored or not stored.get("uncapped"):
        return None
    applied, uncapped = int(stored.get("applied", 0)), int(stored["uncapped"])
    line = f"Pacotes vulneráveis (OSV): \u2212{applied} pontos ({int(stored.get('packages', 0))} pacote(s))"
    if applied < uncapped:      # decidido pelo valor gravado, não pela constante atual
        line += f" \u2014 teto de {applied} aplicado; sem teto seriam \u2212{uncapped}"
    return line


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
