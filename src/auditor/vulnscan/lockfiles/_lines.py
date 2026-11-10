"""Localização de linhas em tempo linear (um índice por arquivo, não uma busca por pacote)."""
from __future__ import annotations

from bisect import bisect_left
from typing import Callable, Hashable


class NextLine:
    """Primeira linha (1-based) a partir do índice ``start`` (0-based) que contém ``needle``."""

    def __init__(self, lines: list[str], needle: str) -> None:
        self._idx = [i for i, ln in enumerate(lines) if needle in ln]

    def after(self, start: int) -> int:
        k = bisect_left(self._idx, start)
        return self._idx[k] + 1 if k < len(self._idx) else start + 1


def first_index(lines: list[str], key_of: Callable[[str], Hashable | None],
                start: int = 0) -> dict[Hashable, int]:
    """``{chave: índice 0-based da 1ª linha com essa chave}`` numa só passada."""
    out: dict[Hashable, int] = {}
    for i in range(start, len(lines)):
        key = key_of(lines[i])
        if key is not None:
            out.setdefault(key, i)
    return out
