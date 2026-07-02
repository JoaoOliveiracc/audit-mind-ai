"""CLI interativo do Audit Mind AI."""
from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Optional

import typer
from langgraph.types import Command
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from . import __version__
from .config import get_settings
from .graph import build_graph
from .llm import LLMConfigError, get_llm, reset_llm_cache

app = typer.Typer(add_completion=False, help="Audit Mind AI — auditoria de projetos com LangGraph.")
console = Console()

_NODE_LABELS = {
    "discovery": "🔎 Descoberta e detecção de stack",
    "plan_questions": "❓ Gerando perguntas de esclarecimento",
    "clarify": "💬 Esclarecimentos",
    "planning": "🗺️  Planejando dimensões de auditoria",
    "audit": "🕵️  Executando investigadores",
    "synthesis": "🧠 Consolidando e pontuando",
    "report": "📄 Gerando relatório",
}


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
            label = _NODE_LABELS.get(node, node)
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
):
    """Executa uma auditoria completa em PATH e emite o relatório final."""
    # Overrides de runtime: definem o ambiente e recarregam a config/modelo.
    if provider:
        os.environ["AUDITOR_PROVIDER"] = provider
    if model:
        os.environ["AUDITOR_MODEL"] = model
    if provider or model:
        get_settings.cache_clear()
        reset_llm_cache()

    settings = get_settings()
    root = Path(path).expanduser().resolve()
    if not root.is_dir():
        console.print(f"[red]Erro:[/red] diretório não encontrado: {root}")
        raise typer.Exit(code=1)

    # Valida credencial/pacote do provedor cedo, com mensagem acionável.
    try:
        get_llm()
    except LLMConfigError as exc:
        console.print(f"[red]Erro de configuração do LLM:[/red] {exc}")
        raise typer.Exit(code=1)

    console.print(
        Panel(
            f"[bold]Audit Mind AI[/bold] v{__version__}\n"
            f"Projeto: [cyan]{root}[/cyan]\n"
            f"Provedor: [cyan]{settings.provider}[/cyan] · Modelo: [cyan]{settings.model}[/cyan]",
            border_style="blue",
        )
    )

    graph = build_graph()
    thread_id = uuid.uuid4().hex
    config = {"configurable": {"thread_id": thread_id}}

    initial = {
        "project_path": str(root),
        "user_goal": goal or "",
        "skip_questions": no_questions,
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
    color = "green" if score >= 75 else "yellow" if score >= 50 else "red"

    table = Table(title="Distribuição de Achados", show_header=True, header_style="bold")
    table.add_column("Severidade")
    table.add_column("Qtde", justify="right")
    counts: dict[str, int] = {}
    for f in findings:
        counts[f.get("severity", "info")] = counts.get(f.get("severity", "info"), 0) + 1
    for sev in ("critical", "high", "medium", "low", "info"):
        table.add_row(sev, str(counts.get(sev, 0)))

    console.print()
    console.print(
        Panel(
            f"Pontuação de saúde: [{color}]{score}/100[/{color}]\n"
            f"Total de achados: {len(findings)}",
            title="✅ Auditoria concluída",
            border_style=color,
        )
    )
    console.print(table)
    console.print(f"\n[bold]Markdown:[/bold] {state.get('report_markdown_path', '—')}")
    console.print(f"[bold]HTML:[/bold]     {state.get('report_html_path', '—')}")


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


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Host da API (padrão: apenas local)."),
    port: int = typer.Option(8020, help="Porta da API."),
    reload: bool = typer.Option(False, "--reload", help="Auto-reload (desenvolvimento)."),
):
    """Sobe a API FastAPI (para o frontend web)."""
    try:
        import uvicorn
    except ImportError:
        console.print("[red]Erro:[/red] dependências da API ausentes. Instale com: pip install -e \".[api]\"")
        raise typer.Exit(code=1)
    console.print(f"[green]Audit Mind AI API[/green] em http://{host}:{port}  (docs em /docs)")
    uvicorn.run("auditor.api.main:app", host=host, port=port, reload=reload)


@app.command()
def version():
    """Mostra a versão do Audit Mind AI."""
    console.print(f"Audit Mind AI v{__version__}")


if __name__ == "__main__":
    app()
