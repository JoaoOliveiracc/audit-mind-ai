"""Nó de verificação determinística de evidência (anti-alucinação, sem LLM).

Para cada achado, confere no disco: o arquivo citado existe? a linha está no
intervalo? o trecho de ``evidence`` realmente aparece no arquivo? Achados cuja
evidência não pode ser localizada (ou cujo arquivo não existe) são **descartados**
como não-substanciados; achados sem arquivo/evidência para conferir têm a
confiança rebaixada. Nada disso consome tokens de LLM.
"""
from __future__ import annotations

import difflib
import re
from pathlib import Path

from rich.console import Console

from ..config import get_settings
from ..state import AuditState
from ..tools.filesystem import _safe_resolve

try:
    from langgraph.config import get_stream_writer
except ImportError:  # pragma: no cover
    get_stream_writer = None

_console = Console(stderr=True)

_WS = re.compile(r"\s+")
_LINENO = re.compile(r"^\s*\d+\|\s?", re.MULTILINE)  # prefixo "  12| " do read_file
_MIN_LINE_LEN = 4  # ignora linhas de evidência triviais ("{", "})", etc.


def _emit(data: dict) -> None:
    if get_stream_writer is None:
        return
    try:
        get_stream_writer()(data)
    except Exception:
        pass


def _normalize(text: str) -> str:
    """Remove numeração de linha e normaliza espaços em branco (preserva o caso)."""
    text = _LINENO.sub("", text)
    return _WS.sub(" ", text).strip()


def _evidence_matches(evidence: str, content: str) -> bool:
    """Heurística tolerante: a evidência aparece no arquivo?"""
    ev = _normalize(evidence)
    if not ev:
        return False
    norm = _normalize(content)
    if ev in norm:
        return True

    # Sobreposição linha-a-linha (tolera reformatação/trechos parciais).
    ev_lines = [_normalize(ln) for ln in evidence.splitlines()]
    ev_lines = [ln for ln in ev_lines if len(ln) >= _MIN_LINE_LEN]
    if ev_lines:
        hits = sum(1 for ln in ev_lines if ln in norm)
        if hits / len(ev_lines) >= 0.5:
            return True

    # Fallback por maior trecho comum (limitado por tamanho para não pesar).
    if len(norm) <= 60_000:
        matcher = difflib.SequenceMatcher(None, ev, norm)
        match = matcher.find_longest_match(0, len(ev), 0, len(norm))
        if match.size >= max(12, int(0.6 * len(ev))):
            return True
    return False


def _verify_finding(finding: dict, root: Path, settings) -> tuple[str, str]:
    """Retorna (status, nota) onde status ∈ {verified, unverified, rejected}."""
    file = finding.get("file")
    evidence = finding.get("evidence")
    line = finding.get("line")

    if not file:
        return "unverified", "sem arquivo citado (achado geral/arquitetural)"

    try:
        target = _safe_resolve(root, str(file))
    except ValueError:
        return "rejected", f"caminho fora do projeto ou inválido: {file}"
    if not target.is_file():
        return "rejected", f"arquivo citado não existe: {file}"

    try:
        if target.stat().st_size > settings.max_file_bytes:
            return "unverified", "arquivo grande demais para verificar"
        content = target.read_text(encoding="utf-8", errors="ignore")
    except OSError as exc:
        return "unverified", f"não foi possível ler o arquivo: {exc}"

    total_lines = content.count("\n") + 1
    line_ok = line is None or (isinstance(line, int) and 1 <= line <= total_lines)

    if evidence and str(evidence).strip():
        if _evidence_matches(str(evidence), content):
            note = "evidência localizada no arquivo"
            return "verified", note if line_ok else note + " (linha fora do intervalo)"
        return "rejected", "evidência não encontrada no arquivo citado (possível alucinação)"

    if not line_ok:
        return "unverified", "arquivo existe, mas linha fora do intervalo e sem evidência"
    return "unverified", "arquivo existe, mas sem trecho de evidência para confirmar"


def verify_node(state: AuditState) -> dict:
    """Filtra achados não-substanciados e anota o status de verificação."""
    settings = get_settings()
    findings = state.get("findings", [])

    if not settings.verify_findings or not findings:
        return {"verification": {"enabled": settings.verify_findings,
                                 "verified": 0, "unverified": 0, "rejected": 0,
                                 "rejected_titles": []},
                "status": "verified"}

    root = Path(state["project_path"]).expanduser().resolve()
    kept: list[dict] = []
    stats = {"enabled": True, "verified": 0, "unverified": 0, "rejected": 0,
             "rejected_titles": []}

    for finding in findings:
        status, note = _verify_finding(finding, root, settings)
        finding["verification_note"] = note
        if status == "rejected":
            stats["rejected"] += 1
            stats["rejected_titles"].append(finding.get("title", "(sem título)"))
            continue
        if status == "verified":
            finding["verified"] = True
            stats["verified"] += 1
        else:  # unverified
            finding["verified"] = False
            finding["confidence"] = min(float(finding.get("confidence", 0.7) or 0.7), 0.5)
            stats["unverified"] += 1
        kept.append(finding)

    _console.print(
        f"[cyan]›[/cyan] Verificação de evidência: "
        f"[green]{stats['verified']} confirmados[/green], "
        f"{stats['unverified']} sem evidência, "
        f"[red]{stats['rejected']} descartados[/red]"
    )
    _emit({"type": "verification", **{k: stats[k] for k in ("verified", "unverified", "rejected")}})

    return {"findings": kept, "verification": stats, "status": "verified"}
