"""Nó de verificação adversarial: um juiz LLM cético tenta refutar cada achado.

Roda após o ``verify`` determinístico (portanto só vê achados cuja evidência já
foi localizada no código). Para cada achado elegível, o juiz reavalia o mérito
do problema relendo o trecho real do arquivo. Achados refutados são descartados;
incertos são mantidos com confiança rebaixada. É opcional (custa tokens) e
escopado por severidade.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from rich.console import Console

from ..config import get_settings
from ..events import emit as _emit  # nome local mantido: ponto de patch dos testes
from ..llm import get_llm
from ..prompts.templates import JUDGE_LENSES, JUDGE_PROMPT, JUDGE_SYSTEM
from ..vulnscan.models import is_deterministic
from ..state import AuditState, Verdict
from ..tools.filesystem import _safe_resolve


_console = Console(stderr=True)

# Ordem de severidade (menor índice = mais grave), para o limiar.
_SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
_CONTEXT_LINES = 40           # janela de linhas ao redor da linha citada
_MAX_CONTEXT_CHARS = 8000     # teto do contexto passado ao juiz




def _eligible(finding: dict, min_rank: int) -> bool:
    """Julga apenas achados com arquivo citado e severidade >= limiar."""
    if not finding.get("file") or is_deterministic(finding):
        return False   # sem arquivo, ou achado determinístico/factual (G48): não vai ao juiz
    rank = _SEVERITY_RANK.get(finding.get("severity", "info"), 4)
    return rank <= min_rank


def _code_context(root: Path, finding: dict, settings) -> str | None:
    """Extrai o trecho real do arquivo citado (janela ao redor da linha)."""
    try:
        target = _safe_resolve(root, str(finding["file"]))
    except ValueError:
        return None
    if not target.is_file():
        return None
    try:
        if target.stat().st_size > settings.max_file_bytes:
            return None
        lines = target.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return None

    line = finding.get("line")
    if isinstance(line, int) and line > 0:
        start = max(0, line - _CONTEXT_LINES)
        end = min(len(lines), line + _CONTEXT_LINES)
        chunk = lines[start:end]
        numbered = "\n".join(f"{start + i + 1:>5}| {ln}" for i, ln in enumerate(chunk))
    else:
        numbered = "\n".join(lines)
    return numbered[:_MAX_CONTEXT_CHARS]


def _judge_once(finding: dict, code_context: str, lens: str, llm) -> Verdict:
    """Um veredito do juiz para um ângulo (lens)."""
    location = finding.get("file") or "—"
    if finding.get("line"):
        location += f":{finding['line']}"
    prompt = JUDGE_PROMPT.format(
        dimension=finding.get("dimension", "—"),
        severity=finding.get("severity", "—"),
        title=finding.get("title", ""),
        description=finding.get("description", ""),
        recommendation=finding.get("recommendation", ""),
        location=location,
        evidence=(finding.get("evidence") or "(sem trecho)"),
        lens=lens,
        code_context=code_context,
    )
    return llm.invoke([SystemMessage(content=JUDGE_SYSTEM), HumanMessage(content=prompt)])


def _judge_votes(finding: dict, code_context: str, votes: int,
                 llm) -> tuple[list[str], str, list[str]]:
    """Coleta os vereditos de um achado (lentes em sequência). Roda numa thread do pool.

    Retorna (vereditos, última justificativa, erros) — falha de uma lente não derruba as demais.
    """
    verdicts: list[str] = []
    rationale = ""
    errors: list[str] = []
    for i in range(votes):
        try:
            v = _judge_once(finding, code_context, JUDGE_LENSES[i], llm)
        except Exception as exc:  # falha do juiz não derruba a auditoria
            errors.append(str(exc))
            continue
        verdicts.append((v.verdict or "uncertain").lower())
        rationale = v.rationale or rationale
    return verdicts, rationale, errors


def _aggregate(verdicts: list[str], votes: int) -> str:
    confirmed = sum(1 for v in verdicts if v == "confirmed")
    refuted = sum(1 for v in verdicts if v == "refuted")
    if refuted > confirmed:
        return "refuted"
    if confirmed > votes / 2:
        return "confirmed"
    return "uncertain"


def adversarial_node(state: AuditState) -> dict:
    """Julga adversarialmente os achados elegíveis; descarta os refutados."""
    settings = get_settings()
    findings = state.get("findings", [])

    disabled_stats = {"enabled": False, "judged": 0, "confirmed": 0,
                      "refuted": 0, "uncertain": 0, "refuted_titles": []}
    if not settings.verify_adversarial or not findings:
        return {"adversarial": disabled_stats, "status": "judged"}

    min_rank = _SEVERITY_RANK.get(settings.adversarial_min_severity.lower(), 1)
    votes = max(1, min(int(settings.adversarial_votes), len(JUDGE_LENSES)))
    root = Path(state["project_path"]).expanduser().resolve()
    llm = get_llm(state.get("provider"), state.get("model")).with_structured_output(Verdict)

    kept: list[dict] = []
    stats: dict[str, Any] = {"enabled": True, "judged": 0, "confirmed": 0, "refuted": 0,
             "uncertain": 0, "refuted_titles": []}

    # G35: os julgamentos (I/O de LLM) rodam em paralelo; a agregação abaixo segue a
    # ordem de entrada, então resultado e estatísticas são idênticos ao modo sequencial.
    contexts = {idx: _code_context(root, f, settings)
                for idx, f in enumerate(findings) if _eligible(f, min_rank)}
    to_judge = {idx: ctx for idx, ctx in contexts.items() if ctx is not None}
    judged: dict[int, tuple[list[str], str, list[str]]] = {}
    if to_judge:
        workers = max(1, min(int(settings.max_concurrent_investigators), len(to_judge)))
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="judge") as pool:
            futures = {pool.submit(_judge_votes, findings[idx], ctx, votes, llm): idx
                       for idx, ctx in to_judge.items()}
            for future in as_completed(futures):
                judged[futures[future]] = future.result()

    for idx, finding in enumerate(findings):
        if idx not in judged:
            kept.append(finding)  # inelegível / sem contexto: passa intacto, sem julgar
            continue

        verdicts, rationale, errors = judged[idx]
        for err in errors:  # console só na thread principal
            _console.print(f"[yellow]  aviso: juiz falhou em '{finding.get('title')}': {err}[/yellow]")

        stats["judged"] += 1
        if not verdicts:
            kept.append(finding)  # sem veredito válido: mantém
            continue

        final = _aggregate(verdicts, votes)
        finding["judge_rationale"] = rationale
        if final == "refuted":
            stats["refuted"] += 1
            stats["refuted_titles"].append(finding.get("title", "(sem título)"))
            continue  # descarta falso positivo
        if final == "confirmed":
            finding["judged"] = "confirmed"
            stats["confirmed"] += 1
        else:  # uncertain
            finding["judged"] = "uncertain"
            finding["confidence"] = min(float(finding.get("confidence", 0.7) or 0.7), 0.5)
            stats["uncertain"] += 1
        kept.append(finding)

    _console.print(
        f"[cyan]›[/cyan] Verificação adversarial: "
        f"[green]{stats['confirmed']} confirmados[/green], "
        f"{stats['uncertain']} incertos, "
        f"[red]{stats['refuted']} refutados[/red] "
        f"(de {stats['judged']} julgados)"
    )
    _emit({"type": "adversarial",
           **{k: stats[k] for k in ("judged", "confirmed", "refuted", "uncertain")}})

    return {"findings": kept, "adversarial": stats, "status": "judged"}
