"""Nó da varredura determinística de dependências e runtimes (G48).

Roda DEPOIS do ``audit`` (que sobrescreve ``findings``) e antes do ``verify``. Opt-in por
execução (AD-003): desligado, não cria nenhum cliente HTTP.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from rich.console import Console

from ..config import get_settings
from ..events import emit as _emit  # nome local: ponto de patch dos testes
from ..state import AuditState
from ..vulnscan.scanner import ScanResult, scan
from ..vulnscan.sources.eol import EndOfLifeClient
from ..vulnscan.sources.osv import OSVClient

_console = Console(stderr=True)


def vuln_scan_enabled(state: AuditState | dict[str, Any]) -> bool:
    """Flag da execução (CLI/API) ou, ausente, ``AUDITOR_VULN_SCAN``."""
    flag = state.get("vuln_scan")
    return bool(get_settings().vuln_scan if flag is None else flag)


def _failed_stats(error: str) -> dict[str, Any]:
    return {"enabled": True, "packages": 0, "queried": 0, "skipped_private": 0, "skipped_files": [],
            "vulnerable": 0, "runtime_findings": 0, "runtime_unknown": 0, "truncated": False,
            "errors": [error]}


def dependency_scan_node(state: AuditState) -> dict:
    if not vuln_scan_enabled(state):
        return {"dependency_scan": {"enabled": False}}
    settings = get_settings()
    clients: list[Any] = []
    try:
        osv = OSVClient()
        clients.append(osv)
        eol = EndOfLifeClient()
        clients.append(eol)
        result = scan(Path(state["project_path"]).expanduser(), settings, osv, eol)
    except Exception as exc:  # noqa: BLE001 — a varredura opcional nunca derruba a auditoria
        result = ScanResult(stats=_failed_stats(f"varredura interrompida: {exc.__class__.__name__}: {exc}"))
    finally:
        for client in clients:
            client.close()
    stats = result.stats
    _console.print(
        f"[cyan]›[/cyan] Varredura de dependências: {stats['queried']} consultada(s), "
        f"[red]{stats['vulnerable']} vulnerável(is)[/red], {stats['runtime_findings']} runtime, "
        f"{stats['skipped_private']} privada(s) puladas"
        + (f", [yellow]{len(stats['errors'])} erro(s)[/yellow]" if stats["errors"] else ""))
    _emit({"type": "dependency_scan", **{k: stats[k] for k in (
        "packages", "queried", "skipped_private", "vulnerable", "runtime_findings", "truncated")},
           "errors": len(stats["errors"])})
    return {"findings": list(state.get("findings") or []) + result.findings, "dependency_scan": stats}
