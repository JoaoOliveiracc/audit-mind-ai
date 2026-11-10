"""Parsers de lockfile (Strategy + Registry).

Cada parser é ``(path, rel, root) -> ParseResult`` e nunca lança: erros viram ``errors``
(LOCK-04). ``REGISTRY`` mapeia o nome do arquivo para o parser.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from ..models import ParseResult

Parser = Callable[[Path, str, Path], ParseResult]
REGISTRY: dict[str, Parser] = {}


def register(*filenames: str) -> Callable[[Parser], Parser]:
    def deco(fn: Parser) -> Parser:
        for name in filenames:
            REGISTRY[name] = fn
        return fn
    return deco


def parser_for(filename: str) -> Parser | None:
    """Parser pelo nome exato do arquivo (requirements*.txt é resolvido pelo módulo Python)."""
    return REGISTRY.get(filename)
