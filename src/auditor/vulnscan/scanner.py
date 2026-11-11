"""Orquestrador da varredura (Facade): lockfiles + runtime → achados e estatísticas.

Puro em relação à rede: recebe os gateways prontos (``osv``/``eol``), o que o torna testável
com dublês. O filtro de privados acontece ANTES de qualquer consulta (LOCK-03, AD-003).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, Sequence

from ..state import Severity
from .lockfiles import composer, npm  # noqa: F401  (registram seus parsers)
from .lockfiles import parser_for
from .lockfiles import python as py_lockfiles
from .models import EOL_SOURCE, MAX_LOCKFILE_BYTES, OSV_SOURCE, Cycle, Dependency, ParseResult, RuntimeDecl
from .runtime import RUNTIME_LABELS, Evaluation, detect_in_file, evaluate, is_runtime_file
from .sources.osv import Advisory, DepKey, dep_key
from .versions import version_key

MAX_PACKAGES = 10_000
_RANK = {s.value: i for i, s in enumerate(Severity)}      # critical=0 … info=4


class VulnSource(Protocol):
    errors: list[str]

    def query(self, deps: Sequence[Dependency]) -> dict[DepKey, list[str]]: ...
    def advisories(self, ids: Any) -> dict[str, Advisory]: ...


class CycleSource(Protocol):
    errors: list[str]

    def cycles(self, product: str) -> list[Cycle] | None: ...


@dataclass
class ScanResult:
    findings: list[dict[str, Any]] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)


def _walk(root: Path, ignore_dirs) -> list[Path]:
    """Arquivos em ordem de caminho, podando ``ignore_dirs`` e sem seguir links (como no G34)."""
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if d not in ignore_dirs)
        # arquivos simbólicos também não: poderiam apontar para fora do projeto (AD-003)
        out.extend(p for f in sorted(filenames) if not (p := Path(dirpath) / f).is_symlink())
    return out


def _parse_file(path: Path, rel: str, root: Path) -> ParseResult | None:
    parser = parser_for(path.name)
    if parser is None and py_lockfiles.is_requirements_file(path.name):
        parser = py_lockfiles.parse_requirements
    if parser is None:
        return None
    try:
        if path.stat().st_size > MAX_LOCKFILE_BYTES:
            return ParseResult(errors=[f"{rel}: lockfile maior que 50 MB, ignorado"])
    except OSError as exc:
        return ParseResult(errors=[f"{rel}: ilegível ({exc})"])
    return parser(path, rel, root)


def _line_text(root: Path, rel: str, line: int, cache: dict[str, list[str]]) -> str:
    if rel not in cache:
        try:
            cache[rel] = (root / rel).read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            cache[rel] = []
    lines = cache[rel]
    return lines[line - 1].strip() if 0 < line <= len(lines) else ""


def _package_finding(occurrences: list[Dependency], advisories: list[Advisory], root: Path,
                     cache: dict[str, list[str]]) -> dict[str, Any]:
    first = occurrences[0]
    severity = min((a.severity for a in advisories), key=lambda s: _RANK.get(s, 99))
    if all(d.dev for d in occurrences):
        severity = "info"   # só desenvolvimento (FND-01)
    fixes = [a.fixed_for(first) for a in advisories]
    fixed = [f for f in fixes if f]
    unfixed = len(fixes) - len(fixed)
    if not fixed:
        recommendation = "Sem correção publicada; avalie substituir/mitigar."
    else:
        target = max(fixed, key=lambda v: version_key(first.ecosystem, v))
        recommendation = f"Atualize para ≥ {target}." if not unfixed else (
            f"Atualize para ≥ {target}; {unfixed} advisory(ies) sem correção publicada — "
            "avalie substituir/mitigar.")
    items = []
    for a in advisories:
        cve = f" ({', '.join(a.cves)})" if a.cves else ""
        note = f" [{a.severity_note}]" if a.severity_note else ""
        items.append(f"- {a.id}{cve} — {a.severity}{note}: {a.summary}")
    others = [f"{d.file}:{d.line}" for d in occurrences[1:]]
    description = (f"{first.name}@{first.version} ({first.ecosystem}) tem advisories conhecidos "
                   f"(fonte: OSV.dev):\n" + "\n".join(items))
    if others:
        description += "\nTambém presente em: " + ", ".join(others)
    return {"dimension": "dependencies", "source": OSV_SOURCE,
            "title": f"{first.name}@{first.version} com {len(advisories)} vulnerabilidade(s) conhecida(s)",
            "severity": severity, "description": description, "recommendation": recommendation,
            "file": first.file, "line": first.line,
            "evidence": _line_text(root, first.file, first.line, cache),
            "confidence": 1.0, "advisories": [a.id for a in advisories]}


def _runtime_finding(decl: RuntimeDecl, result: Evaluation, cycles: list[Cycle]) -> dict[str, Any]:
    label = RUNTIME_LABELS.get(decl.product, decl.product)
    if result.reason == "patch":       # ciclo suportado: basta o último patch do mesmo ciclo
        recommendation = f"Atualize para {label} {result.latest} (último patch do ciclo)."
        title = "atualização recomendada"
    else:                              # EOL: o ciclo suportado mais novo
        supported = next((c for c in cycles if not c.is_eol), None)
        target = f"{label} {supported.name} ({supported.latest})" if supported and supported.latest \
            else "um ciclo suportado"
        recommendation, title = f"Atualize para {target}.", "sem suporte"
    return {"dimension": "dependencies", "source": EOL_SOURCE,
            "title": f"Runtime {label} {decl.value}: {title}",
            "severity": result.severity, "description": result.message + " (fonte: endoflife.date)",
            "recommendation": recommendation,
            "file": decl.file, "line": decl.line, "evidence": decl.evidence, "confidence": 1.0}


def scan(root: Path, settings: Any, osv: VulnSource, eol: CycleSource,
         max_packages: int = MAX_PACKAGES) -> ScanResult:
    root = root.resolve()
    errors: list[str] = []
    skipped_files: list[str] = []
    deps: list[Dependency] = []
    decls: list[RuntimeDecl] = []
    for path in _walk(root, settings.ignore_dirs):
        rel = path.relative_to(root).as_posix()
        try:   # um arquivo malformado nunca descarta o resultado dos demais
            parsed = _parse_file(path, rel, root)
            if parsed is not None:
                deps.extend(parsed.dependencies)
                errors.extend(parsed.errors)
                skipped_files.extend(parsed.skipped_files)
            if is_runtime_file(path.name):
                decls.extend(detect_in_file(path, rel))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{rel}: falha ao ler ({exc.__class__.__name__}: {exc})")

    by_key: dict[DepKey, list[Dependency]] = {}
    for dep in deps:
        by_key.setdefault(dep_key(dep), []).append(dep)
    private_keys = {k for k, occ in by_key.items() if any(d.private for d in occ)}
    public_keys = [k for k in by_key if k not in private_keys]
    truncated = len(public_keys) > max_packages
    queried_keys = public_keys[:max_packages]
    queried = [by_key[k][0] for k in queried_keys]

    hits = osv.query(queried) if queried else {}
    advisories = osv.advisories({i for ids in hits.values() for i in ids}) if hits else {}
    cache: dict[str, list[str]] = {}
    findings = []
    for key in queried_keys:
        found = [advisories[i] for i in dict.fromkeys(hits.get(key, [])) if i in advisories]
        if found:
            findings.append(_package_finding(by_key[key], found, root, cache))
    vulnerable = len(findings)

    runtime_findings = runtime_unknown = 0
    for decl in decls:
        cycles = eol.cycles(decl.product)
        result = evaluate(decl, cycles)
        if result.status == "finding" and cycles and result.severity:
            findings.append(_runtime_finding(decl, result, cycles))
            runtime_findings += 1
        elif result.status == "unknown":
            runtime_unknown += 1

    stats = {"enabled": True, "packages": len(by_key), "queried": len(queried),
             "skipped_private": len(private_keys), "skipped_files": skipped_files,
             "vulnerable": vulnerable, "runtime_findings": runtime_findings,
             "runtime_unknown": runtime_unknown, "truncated": truncated,
             "errors": errors + list(osv.errors) + list(eol.errors)}
    return ScanResult(findings=findings, stats=stats)
