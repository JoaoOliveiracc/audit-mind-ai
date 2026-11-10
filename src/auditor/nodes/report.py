"""Nó de relatório: renderiza e grava os arquivos Markdown e HTML."""
from __future__ import annotations

from pathlib import Path

from langchain_core.runnables import RunnableConfig

from ..config import get_settings
from ..report.renderer import write_reports
from ..state import AuditState


def report_node(state: AuditState, config: RunnableConfig) -> dict:
    """Gera os relatórios finais e retorna seus caminhos.

    O ``thread_id`` (= id da auditoria na API / uuid da CLI) entra no nome dos arquivos.
    """
    settings = get_settings()
    output_dir = Path(settings.output_dir).expanduser().resolve()
    thread_id = (config.get("configurable") or {}).get("thread_id")
    md_path, html_path, sarif_path = write_reports(dict(state), output_dir,
                                                   run_id=str(thread_id) if thread_id else None)
    return {
        "report_markdown_path": str(md_path),
        "report_html_path": str(html_path),
        "report_sarif_path": str(sarif_path),
        "status": "completed",
    }
