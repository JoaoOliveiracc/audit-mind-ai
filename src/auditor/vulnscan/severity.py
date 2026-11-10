"""Severidade de um advisory OSV: rótulo da base → CVSS v3.x → ``medium`` + nota (puro)."""
from __future__ import annotations

import math
from typing import Any

_LABELS = {"LOW": "low", "MODERATE": "medium", "MEDIUM": "medium", "HIGH": "high",
           "CRITICAL": "critical"}
UNKNOWN_NOTE = "severidade não informada pela fonte"

# Métricas da especificação CVSS v3.1 (FIRST), seção 7.4.
_AV = {"N": 0.85, "A": 0.62, "L": 0.55, "P": 0.2}
_AC = {"L": 0.77, "H": 0.44}
_PR_U = {"N": 0.85, "L": 0.62, "H": 0.27}
_PR_C = {"N": 0.85, "L": 0.68, "H": 0.5}
_UI = {"N": 0.85, "R": 0.62}
_CIA = {"H": 0.56, "L": 0.22, "N": 0.0}


def _roundup(x: float) -> float:
    """Roundup da especificação 3.1 (Apêndice A), imune a erro de ponto flutuante."""
    i = round(x * 100_000)
    return i / 100_000.0 if i % 10_000 == 0 else (math.floor(i / 10_000) + 1) / 10.0


def cvss3_base_score(vector: str) -> float | None:
    """Nota base de um vetor ``CVSS:3.0/…`` ou ``CVSS:3.1/…``; ``None`` se inválido/outra versão."""
    parts = vector.split("/")
    if not parts or parts[0] not in ("CVSS:3.0", "CVSS:3.1"):
        return None
    try:
        m = dict(p.split(":", 1) for p in parts[1:])
        scope_changed = m["S"] == "C"
        if m["S"] not in ("U", "C"):
            return None
        av, ac, ui = _AV[m["AV"]], _AC[m["AC"]], _UI[m["UI"]]
        pr = (_PR_C if scope_changed else _PR_U)[m["PR"]]
        c, i, a = _CIA[m["C"]], _CIA[m["I"]], _CIA[m["A"]]
    except (KeyError, ValueError):
        return None
    iss = 1 - (1 - c) * (1 - i) * (1 - a)
    impact = 7.52 * (iss - 0.029) - 3.25 * (iss - 0.02) ** 15 if scope_changed else 6.42 * iss
    if impact <= 0:
        return 0.0
    exploitability = 8.22 * av * ac * pr * ui
    total = 1.08 * (impact + exploitability) if scope_changed else impact + exploitability
    return _roundup(min(total, 10.0))


def severity_from_score(score: float) -> str:
    """Faixas qualitativas do CVSS v3: 0 → info; <4 low; <7 medium; <9 high; ≥9 critical."""
    if score == 0:
        return "info"
    if score < 4.0:
        return "low"
    if score < 7.0:
        return "medium"
    return "high" if score < 9.0 else "critical"


def severity_from_osv(record: dict[str, Any]) -> tuple[str, str | None]:
    """(severidade, nota). Precedência: rótulo da base → maior CVSS v3 → ``medium`` + nota."""
    label = str((record.get("database_specific") or {}).get("severity") or "").upper()
    if label in _LABELS:
        return _LABELS[label], None
    scores = [s for s in (cvss3_base_score(str(e.get("score", "")))
                          for e in record.get("severity") or [] if e.get("type") == "CVSS_V3")
              if s is not None]
    if scores:
        return severity_from_score(max(scores)), None
    return "medium", UNKNOWN_NOTE
