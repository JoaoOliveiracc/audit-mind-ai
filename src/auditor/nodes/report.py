"""Nó de relatório: renderiza e grava os arquivos Markdown e HTML."""
from __future__ import annotations

from pathlib import Path

from ..config import get_settings
from ..report.renderer import write_reports
from ..state import AuditState


def report_node(state: AuditState) -> dict:
    """Gera os relatórios finais e retorna seus caminhos."""
    settings = get_settings()
    output_dir = Path(settings.output_dir).expanduser().resolve()
    md_path, html_path = write_reports(dict(state), output_dir)
    return {
        "report_markdown_path": str(md_path),
        "report_html_path": str(html_path),
        "status": "completed",
    }
