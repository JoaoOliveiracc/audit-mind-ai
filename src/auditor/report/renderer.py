"""Renderização do relatório de auditoria em Markdown e HTML."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from ..state import Severity

_TEMPLATE_DIR = Path(__file__).parent / "templates"

SEVERITY_ORDER = [
    Severity.CRITICAL.value,
    Severity.HIGH.value,
    Severity.MEDIUM.value,
    Severity.LOW.value,
    Severity.INFO.value,
]
SEVERITY_LABEL = {
    "critical": "Crítico", "high": "Alto", "medium": "Médio",
    "low": "Baixo", "info": "Informativo",
}


def _sort_findings(findings: list[dict]) -> list[dict]:
    rank = {s: i for i, s in enumerate(SEVERITY_ORDER)}
    return sorted(findings, key=lambda f: (rank.get(f.get("severity", "info"), 99), f.get("dimension", "")))


def build_context(state: dict[str, Any], generated_at: str) -> dict[str, Any]:
    """Monta o contexto de template a partir do estado final do grafo."""
    findings = _sort_findings(state.get("findings", []))
    counts = {s: 0 for s in SEVERITY_ORDER}
    for f in findings:
        counts[f.get("severity", "info")] = counts.get(f.get("severity", "info"), 0) + 1

    profile = state.get("stack_profile", {})
    return {
        "generated_at": generated_at,
        "project_path": state.get("project_path", ""),
        "user_goal": state.get("user_goal", ""),
        "user_context": state.get("user_context", {}),
        "health_score": state.get("health_score", 0),
        "executive_summary": state.get("executive_summary", ""),
        "stack_profile": profile,
        "plan": state.get("plan", {}),
        "dimension_summaries": state.get("dimension_summaries", []),
        "findings": findings,
        "counts": counts,
        "severity_order": SEVERITY_ORDER,
        "severity_label": SEVERITY_LABEL,
        "total_findings": len(findings),
    }


def render_markdown(ctx: dict[str, Any]) -> str:
    """Gera o relatório em Markdown."""
    lines: list[str] = []
    a = lines.append
    a(f"# Relatório de Auditoria — Audit Mind AI\n")
    a(f"- **Projeto:** `{ctx['project_path']}`")
    a(f"- **Gerado em:** {ctx['generated_at']}")
    a(f"- **Pontuação de saúde:** {ctx['health_score']}/100")
    a(f"- **Total de achados:** {ctx['total_findings']}")
    if ctx["user_goal"]:
        a(f"- **Objetivo informado:** {ctx['user_goal']}")
    a("")

    a("## Resumo Executivo\n")
    a(ctx["executive_summary"] or "_(não gerado)_")
    a("")

    a("## Distribuição por Severidade\n")
    a("| Severidade | Quantidade |")
    a("| --- | --- |")
    for sev in ctx["severity_order"]:
        a(f"| {ctx['severity_label'][sev]} | {ctx['counts'].get(sev, 0)} |")
    a("")

    profile = ctx["stack_profile"]
    a("## Perfil Técnico Detectado\n")
    if profile:
        langs = ", ".join(f"{k} ({v})" for k, v in (profile.get("languages") or {}).items()) or "—"
        a(f"- **Linguagens:** {langs}")
        a(f"- **Frameworks/ecossistemas:** {', '.join(profile.get('frameworks') or []) or '—'}")
        a(f"- **Gerenciadores de pacote:** {', '.join(profile.get('package_managers') or []) or '—'}")
        a(f"- **Arquivos:** {profile.get('total_files', 0)} | **LOC (aprox.):** {profile.get('total_loc', 0)}")
        a(f"- **Testes:** {'sim' if profile.get('has_tests') else 'não'} | "
          f"**CI:** {'sim' if profile.get('has_ci') else 'não'} | "
          f"**Docker:** {'sim' if profile.get('has_docker') else 'não'} | "
          f"**Git:** {'sim' if profile.get('has_git') else 'não'}")
    a("")

    a("## Resumo por Dimensão\n")
    for d in ctx["dimension_summaries"]:
        a(f"### {d.get('dimension', '?').title()}\n")
        a(d.get("summary", ""))
        a("")

    a("## Achados Detalhados\n")
    if not ctx["findings"]:
        a("_Nenhum achado registrado._\n")
    for i, f in enumerate(ctx["findings"], start=1):
        sev = ctx["severity_label"].get(f.get("severity", "info"), f.get("severity", ""))
        a(f"### {i}. [{sev}] {f.get('title', 'Sem título')}\n")
        a(f"- **Dimensão:** {f.get('dimension', '—')}")
        loc = f.get("file") or "—"
        if f.get("line"):
            loc += f":{f['line']}"
        a(f"- **Local:** `{loc}`")
        a(f"- **Confiança:** {f.get('confidence', 0):.0%}")
        a("")
        a(f"**Descrição:** {f.get('description', '')}\n")
        if f.get("evidence"):
            a("**Evidência:**\n")
            a("```")
            a(str(f["evidence"]).strip())
            a("```")
        a(f"\n**Recomendação:** {f.get('recommendation', '')}\n")
    return "\n".join(lines)


def render_html(ctx: dict[str, Any]) -> str:
    """Gera o relatório em HTML (auto-contido, com CSS embutido)."""
    # autoescape=True (incondicional): o conteúdo dos achados vem de código
    # auditado (potencialmente malicioso). Sem escape, um repositório hostil
    # poderia injetar <script> no relatório HTML (XSS armazenado). O template
    # termina em '.j2', então select_autoescape por extensão NÃO ativaria o escape.
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=True,
    )
    template = env.get_template("report.html.j2")
    return template.render(**ctx)


def write_reports(state: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    """Renderiza e grava os relatórios Markdown e HTML; retorna os caminhos."""
    output_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    stamp = now.strftime("%Y%m%d-%H%M%S")
    ctx = build_context(state, generated_at=now.strftime("%Y-%m-%d %H:%M:%S"))

    md_path = output_dir / f"auditoria-{stamp}.md"
    html_path = output_dir / f"auditoria-{stamp}.html"
    md_path.write_text(render_markdown(ctx), encoding="utf-8")
    html_path.write_text(render_html(ctx), encoding="utf-8")
    return md_path, html_path
