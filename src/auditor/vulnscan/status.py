"""Linha de status explícita da varredura (RPT-01): ausência de achados nunca soa como "seguro"."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .scanner import MAX_PACKAGES

DISABLED = "Verificação de dependências desativada (AUDITOR_VULN_SCAN)"
INCOMPLETE = "Varredura de dependências incompleta"


@dataclass(frozen=True)
class ScanStatus:
    headline: str
    incomplete: bool = False
    reasons: list[str] = field(default_factory=list)


def scan_status(stats: Mapping[str, Any] | None) -> ScanStatus:
    if not stats or not stats.get("enabled"):
        return ScanStatus(DISABLED)
    queried, vulnerable = stats.get("queried", 0), stats.get("vulnerable", 0)
    private = stats.get("skipped_private", 0)
    suffix = f" ({private} privada(s) não consultada(s))" if private else ""
    runtime, unknown = stats.get("runtime_findings", 0), stats.get("runtime_unknown", 0)
    if runtime:
        suffix += f"; {runtime} alerta(s) de runtime"
    if unknown:
        suffix += f"; {unknown} declaração(ões) de runtime não avaliada(s)"
    reasons = []
    if stats.get("truncated"):
        reasons.append(f"limite de {MAX_PACKAGES:_} pacotes atingido; o restante não foi consultado"
                       .replace("_", " "))
    reasons.extend(f"arquivo não consultado (origem privada/indeterminada): {f}"
                   for f in stats.get("skipped_files") or [])
    reasons.extend(str(e) for e in stats.get("errors") or [])
    if reasons:
        return ScanStatus(INCOMPLETE + suffix, True, reasons)
    if vulnerable:
        return ScanStatus(f"{vulnerable} pacote(s) vulnerável(is) entre {queried} dependências "
                          f"consultadas{suffix}")
    return ScanStatus(f"Nenhuma vulnerabilidade conhecida nas {queried} dependências consultadas{suffix}")
