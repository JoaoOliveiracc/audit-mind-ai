"""Objetos de valor da varredura (imutáveis)."""
from __future__ import annotations

from typing import Any, Mapping

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Dependency:
    """Pacote instalado segundo um lockfile."""

    ecosystem: str          # "npm" | "Packagist" | "PyPI" (strings do schema OSV)
    name: str
    version: str
    file: str               # caminho relativo à raiz do projeto
    line: int               # 1-based: linha que carrega a versão (LOCK-01)
    dev: bool = False
    private: bool = False   # True ⇒ nunca consultado (LOCK-03)


@dataclass(frozen=True)
class RuntimeDecl:
    """Runtime declarado no projeto (RT-01)."""

    product: str            # slug do endoflife.date: "nodejs" | "php" | "python"
    value: str              # como declarado (ex.: "20.11.1", ">=18", "8.1")
    file: str
    line: int
    evidence: str           # a linha exata do arquivo


@dataclass(frozen=True)
class Cycle:
    """Ciclo de release de um runtime (endoflife.date)."""

    name: str               # "20" (Node) | "8.1" (PHP) | "3.11" (Python)
    is_eol: bool
    latest: str | None


@dataclass
class ParseResult:
    """Saída de um parser: dependências + arquivos pulados/erros (LOCK-03/04)."""

    dependencies: list[Dependency] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    skipped_files: list[str] = field(default_factory=list)


# Achados determinísticos (G48): factuais, citam lockfiles — não vão ao juiz adversarial e o
# verify aceita arquivos até MAX_LOCKFILE_BYTES para eles.
DETERMINISTIC_SOURCES = frozenset({"osv", "endoflife"})
MAX_LOCKFILE_BYTES = 50 * 1024 * 1024


def is_deterministic(finding: Mapping[str, Any]) -> bool:
    return finding.get("source") in DETERMINISTIC_SOURCES
