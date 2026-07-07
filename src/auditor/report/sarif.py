"""Exportação dos achados em SARIF 2.1.0.

SARIF (Static Analysis Results Interchange Format) é o formato consumido pelo
**GitHub Code Scanning**, GitLab e várias ferramentas de CI. Emitir SARIF permite
publicar os achados da auditoria como *code scanning alerts* (anotações inline no
PR/arquivo) via `github/codeql-action/upload-sarif`.

Referência: https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html
"""
from __future__ import annotations

import json
from typing import Any

from .. import __version__

# Severidade do achado -> nível SARIF (error | warning | note).
_SARIF_LEVEL = {
    "critical": "error",
    "high": "error",
    "medium": "warning",
    "low": "note",
    "info": "note",
}

_INFORMATION_URI = "https://github.com/JoaoOliveiracc/audit-mind-ai"


def _rule_id(dimension: str | None) -> str:
    """ID de regra estável por dimensão (ex.: ``audit-mind/security``)."""
    return f"audit-mind/{dimension or 'general'}"


def _uri(path: str) -> str:
    """Normaliza o caminho do arquivo para URI relativa à raiz do projeto."""
    p = str(path).replace("\\", "/")
    return p[2:] if p.startswith("./") else p


def _message(finding: dict) -> str:
    """Texto do alerta: título + descrição + recomendação."""
    parts = [finding.get("title", "").strip()]
    if finding.get("description"):
        parts.append(str(finding["description"]).strip())
    if finding.get("recommendation"):
        parts.append(f"Recomendação: {str(finding['recommendation']).strip()}")
    return "\n\n".join(p for p in parts if p) or "(sem descrição)"


def _rules(findings: list[dict]) -> list[dict]:
    """Uma regra SARIF por dimensão presente nos achados (ordem preservada)."""
    rules: list[dict] = []
    seen: set[str] = set()
    for f in findings:
        dim = f.get("dimension") or "general"
        if dim in seen:
            continue
        seen.add(dim)
        rules.append(
            {
                "id": _rule_id(dim),
                "name": "".join(part.capitalize() for part in dim.split("_")),
                "shortDescription": {"text": f"Achados de auditoria — dimensão '{dim}'."},
            }
        )
    return rules


def _result(finding: dict) -> dict:
    """Converte um achado num ``result`` SARIF."""
    sev = finding.get("severity", "info")
    result: dict[str, Any] = {
        "ruleId": _rule_id(finding.get("dimension")),
        "level": _SARIF_LEVEL.get(sev, "note"),
        "message": {"text": _message(finding)},
        "properties": {
            "severity": sev,
            "confidence": finding.get("confidence"),
            "recommendation": finding.get("recommendation", ""),
            "verified": finding.get("verified"),
            "judged": finding.get("judged"),
        },
    }

    file = finding.get("file")
    if file:
        physical: dict[str, Any] = {"artifactLocation": {"uri": _uri(file)}}
        line = finding.get("line")
        if isinstance(line, int) and line > 0:
            physical["region"] = {"startLine": line}
        result["locations"] = [{"physicalLocation": physical}]
    return result


def build_sarif(state: dict) -> dict:
    """Monta o documento SARIF 2.1.0 a partir do estado final do grafo."""
    findings = state.get("findings", [])
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "Audit Mind AI",
                        "informationUri": _INFORMATION_URI,
                        "version": __version__,
                        "rules": _rules(findings),
                    }
                },
                "results": [_result(f) for f in findings],
            }
        ],
    }


def render_sarif(state: dict) -> str:
    """Serializa o documento SARIF do estado em JSON (string)."""
    return json.dumps(build_sarif(state), ensure_ascii=False, indent=2)
