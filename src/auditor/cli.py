"""CLI interativo do Audit Mind AI."""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Optional

import typer
from langgraph.types import Command
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from . import __version__
from .config import get_settings
from .events import NODE_ICONS, NODE_LABELS
from .scoring import dependency_penalty_line, severity_counts
from .graph import build_graph
from .nodes.dependency_scan import resolve_vuln_scan
from .vulnscan.status import scan_status
from .llm import LLMConfigError, get_llm
from .logging_config import setup_logging

app = typer.Typer(add_completion=False, help="Audit Mind AI — auditoria de projetos com LangGraph.")
console = Console()



@app.callback()
def _main() -> None:
    """Inicializa o logging (nível via AUDITOR_LOG_LEVEL) antes de qualquer comando."""
    setup_logging(get_settings().log_level)


def _ask_clarifying_questions(interrupts) -> dict[str, str]:
    """Renderiza as perguntas e coleta as respostas do usuário no terminal."""
    payload = interrupts[0].value
    questions = payload.get("questions", [])
    console.print(
        Panel(
            "O agent precisa de alguns esclarecimentos para focar a auditoria.\n"
            "Responda o que puder — pressione Enter para pular uma pergunta.",
            title="💬 Esclarecimentos",
            border_style="cyan",
        )
    )
    answers: dict[str, str] = {}
    for i, q in enumerate(questions, start=1):
        console.print(f"\n[bold cyan]{i}. {q['question']}[/bold cyan]")
        if q.get("rationale"):
            console.print(f"   [dim]{q['rationale']}[/dim]")
        ans = Prompt.ask("   ↳ resposta", default="", show_default=False)
        answers[q["question"]] = ans or "(sem resposta)"
    return answers


def _run(graph, inp, config):
    """Consome o stream do grafo, exibindo o progresso e tratando interrupções.

    Retorna a lista de interrupts se o grafo pausou, ou ``None`` se concluiu.
    """
    for chunk in graph.stream(inp, config, stream_mode="updates"):
        if "__interrupt__" in chunk:
            return chunk["__interrupt__"]
        for node in chunk:
            label = f"{NODE_ICONS.get(node, '•')} {NODE_LABELS.get(node, node)}"
            console.print(f"[green]✓[/green] {label}")
    return None


@app.command()
def audit(
    path: str = typer.Argument(..., help="Caminho do projeto a auditar."),
    goal: Optional[str] = typer.Option(
        None, "--goal", "-g", help="Objetivo/contexto da auditoria (opcional)."
    ),
    no_questions: bool = typer.Option(
        False, "--no-questions", help="Pula a fase de esclarecimentos (modo não interativo)."
    ),
    provider: Optional[str] = typer.Option(
        None, "--provider", "-p",
        help="Provedor de LLM (anthropic, openai, groq, google_genai, ollama, …).",
    ),
    model: Optional[str] = typer.Option(
        None, "--model", "-m", help="Modelo a usar (sobrescreve AUDITOR_MODEL)."
    ),
    vuln_scan: Optional[bool] = typer.Option(
        None, "--vuln-scan/--no-vuln-scan",
        help="Verifica dependências/runtimes vulneráveis (envia nomes e versões de pacotes públicos "
             "ao OSV.dev e ao endoflife.date). Padrão: AUDITOR_VULN_SCAN.",
    ),
):
    """Executa uma auditoria completa em PATH e emite o relatório final."""
    # Provedor/modelo efetivos: flag da CLI ou default das settings. Passados via
    # estado do grafo (sem mutar os.environ global).
    settings = get_settings()
    eff_provider = provider or settings.provider
    eff_model = model or settings.model

    root = Path(path).expanduser().resolve()
    if not root.is_dir():
        console.print(f"[red]Erro:[/red] diretório não encontrado: {root}")
        raise typer.Exit(code=1)

    # Valida credencial/pacote do provedor cedo, com mensagem acionável.
    try:
        get_llm(eff_provider, eff_model)
    except LLMConfigError as exc:
        console.print(f"[red]Erro de configuração do LLM:[/red] {exc}")
        raise typer.Exit(code=1)

    console.print(
        Panel(
            f"[bold]Audit Mind AI[/bold] v{__version__}\n"
            f"Projeto: [cyan]{root}[/cyan]\n"
            f"Provedor: [cyan]{eff_provider}[/cyan] · Modelo: [cyan]{eff_model}[/cyan]",
            border_style="blue",
        )
    )

    graph = build_graph()
    thread_id = uuid.uuid4().hex
    config = {"configurable": {"thread_id": thread_id}}

    initial = {
        "project_path": str(root),
        "user_goal": goal or "",
        "provider": eff_provider,
        "model": eff_model,
        "skip_questions": no_questions,
        "vuln_scan": resolve_vuln_scan(vuln_scan),
        "user_context": {},
        "findings": [],
        "dimension_summaries": [],
        "status": "started",
    }

    try:
        interrupts = _run(graph, initial, config)
        while interrupts is not None:
            if no_questions:
                interrupts = _run(graph, Command(resume={}), config)
                continue
            answers = _ask_clarifying_questions(interrupts)
            console.print()
            interrupts = _run(graph, Command(resume=answers), config)
    except KeyboardInterrupt:
        console.print("\n[yellow]Auditoria interrompida pelo usuário.[/yellow]")
        raise typer.Exit(code=130)
    except Exception as exc:  # noqa: BLE001
        console.print(f"\n[red]Falha na auditoria:[/red] {exc}")
        raise typer.Exit(code=1)

    final = graph.get_state(config).values
    _print_summary(final)


def _print_summary(state: dict) -> None:
    """Imprime o resumo final e os caminhos dos relatórios."""
    score = state.get("health_score", 0)
    findings = state.get("findings", [])
    explanation = dependency_penalty_line(state.get("dependency_penalty"))
    color = "green" if score >= 75 else "yellow" if score >= 50 else "red"

    table = Table(title="Distribuição de Achados", show_header=True, header_style="bold")
    table.add_column("Severidade")
    table.add_column("Qtde", justify="right")
    counts = severity_counts(findings)
    for sev in ("critical", "high", "medium", "low", "info"):
        table.add_row(sev, str(counts[sev]))

    console.print()
    console.print(
        Panel(
            f"Pontuação de saúde: [{color}]{score}/100[/{color}]\n"
            + (f"{escape(explanation)}\n" if explanation else "")
            + f"Total de achados: {len(findings)}",
            title="✅ Auditoria concluída",
            border_style=color,
        )
    )
    console.print(table)

    status = scan_status(state.get("dependency_scan"))
    color_dep = "yellow" if status.incomplete else "cyan"
    console.print(f"\n[bold]Dependências:[/bold] [{color_dep}]{escape(status.headline)}[/{color_dep}]")
    for reason in status.reasons:
        console.print(f"  - {escape(reason)}")

    v = state.get("verification") or {}
    if v.get("enabled"):
        console.print(
            f"\n[bold]Verificação de evidência:[/bold] "
            f"[green]{v.get('verified', 0)} confirmados[/green], "
            f"{v.get('unverified', 0)} sem evidência, "
            f"[red]{v.get('rejected', 0)} descartados[/red]"
        )

    adv = state.get("adversarial") or {}
    if adv.get("enabled"):
        console.print(
            f"[bold]Verificação adversarial:[/bold] "
            f"[green]{adv.get('confirmed', 0)} confirmados[/green], "
            f"{adv.get('uncertain', 0)} incertos, "
            f"[red]{adv.get('refuted', 0)} refutados[/red]"
        )

    console.print(f"\n[bold]Markdown:[/bold] {state.get('report_markdown_path', '—')}")
    console.print(f"[bold]HTML:[/bold]     {state.get('report_html_path', '—')}")
    console.print(f"[bold]SARIF:[/bold]    {state.get('report_sarif_path', '—')}")


@app.command()
def providers():
    """Lista os provedores de LLM suportados e o pacote/credencial de cada um."""
    from .config import PROVIDER_ENV_VAR, PROVIDER_PACKAGE

    table = Table(title="Provedores de LLM suportados", show_header=True, header_style="bold")
    table.add_column("Provedor")
    table.add_column("Pacote")
    table.add_column("Credencial (env)")
    for prov in PROVIDER_PACKAGE:
        env = PROVIDER_ENV_VAR.get(prov) or "— (local/AWS/gcloud)"
        table.add_row(prov, PROVIDER_PACKAGE[prov], env)
    console.print(table)
    console.print(
        "\nUse: [cyan]auditor audit <dir> --provider <nome> --model <modelo>[/cyan]"
    )


_LOCAL_BIND_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Host da API (padrão: apenas local)."),
    port: int = typer.Option(8020, help="Porta da API."),
    reload: bool = typer.Option(False, "--reload", help="Auto-reload (desenvolvimento)."),
    allow_remote: bool = typer.Option(
        False, "--allow-remote",
        help="Permite bind em interface não-local (a API NÃO tem autenticação).",
    ),
):
    """Sobe a API FastAPI (para o frontend web)."""
    # AD-002: a API lê o filesystem do host e não tem autenticação — exposição
    # fora do loopback só com opt-in explícito.
    if host not in _LOCAL_BIND_HOSTS:
        if not allow_remote:
            console.print(
                f"[red]Recusado:[/red] '{host}' não é uma interface local e a API não tem "
                "autenticação. Use --allow-remote se a exposição for intencional."
            )
            raise typer.Exit(code=2)
        console.print(
            f"[bold yellow]Aviso:[/bold yellow] API exposta em '{host}' sem autenticação. "
            "Clientes remotos só são aceitos se o host deles estiver em AUDITOR_ALLOWED_HOSTS."
        )
    try:
        import uvicorn
    except ImportError:
        console.print("[red]Erro:[/red] dependências da API ausentes. Instale com: pip install -e \".[api]\"")
        raise typer.Exit(code=1)
    console.print(f"[green]Audit Mind AI API[/green] em http://{host}:{port}  (docs em /docs)")
    uvicorn.run("auditor.api.main:app", host=host, port=port, reload=reload)


db_app = typer.Typer(help="Manutenção do banco local da API (AUDITOR_DATA_DIR, padrão ~/.config/auditor).")
app.add_typer(db_app, name="db")


@db_app.command("compact")
def db_compact(
    db: Optional[Path] = typer.Option(
        None, "--db", help="Banco de checkpoints (padrão: $AUDITOR_DATA_DIR/audits-checkpoints.sqlite)."
    ),
):
    """Remove checkpoints de sub-agentes (legado) e compacta o banco. Rode com a API parada."""
    import sqlite3

    try:
        from .api.retention import compact_checkpoints
        from .api.store import checkpoint_db_path
    except ImportError:
        console.print("[red]Erro:[/red] dependências da API ausentes. Instale com: pip install -e \".[api]\"")
        raise typer.Exit(code=1)

    target = db or checkpoint_db_path()
    if not target.is_file():
        console.print(f"Nada a compactar: {target} não existe.")
        return
    try:
        stats = compact_checkpoints(target)
    except sqlite3.OperationalError as exc:
        if "locked" in str(exc).lower():
            console.print("[red]Banco em uso[/red] — pare a API (auditor serve) e tente novamente.")
        else:
            console.print(f"[red]Erro ao compactar {target}:[/red] {exc}")
        raise typer.Exit(code=1)

    mb = 1024 * 1024
    console.print(f"Checkpoints de sub-agentes removidos: {stats.removed_checkpoints}")
    console.print(f"Writes de sub-agentes removidos: {stats.removed_writes}")
    console.print(f"Tamanho: {stats.size_before / mb:.1f} MB → {stats.size_after / mb:.1f} MB")


@app.command()
def version():
    """Mostra a versão do Audit Mind AI."""
    console.print(f"Audit Mind AI v{__version__}")


if __name__ == "__main__":
    app()
