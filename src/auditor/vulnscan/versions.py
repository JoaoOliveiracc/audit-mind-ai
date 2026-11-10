"""Comparação de versões e normalização de nomes por ecossistema (puro)."""
from __future__ import annotations

import re
from typing import Any

from packaging.version import InvalidVersion, Version

_PEP503 = re.compile(r"[-_.]+")


def normalize_name(ecosystem: str, name: str) -> str:
    """PyPI: PEP 503 (minúsculas; ``-``/``_``/``.`` → ``-``). npm/Packagist: como escrito."""
    return _PEP503.sub("-", name).lower() if ecosystem == "PyPI" else name


def _semverish_key(v: str) -> tuple[Any, ...]:
    """Chave para npm/Packagist: ``v`` opcional, núcleo numérico, pré-release < release."""
    v = v.strip().lstrip("vV").split("+", 1)[0]
    core, _, pre = v.partition("-")
    nums = []
    for part in core.split("."):
        digits = re.match(r"\d+", part)
        nums.append(int(digits.group()) if digits else 0)
    nums += [0] * (4 - len(nums))
    pre_key = tuple((0, int(p)) if p.isdigit() else (1, p) for p in pre.split(".")) if pre else ()
    return (tuple(nums), 0 if pre else 1, pre_key)


_COMPOSER_STABILITY = {"dev": 0, "alpha": 1, "a": 1, "beta": 2, "b": 2, "rc": 3}
_COMPOSER_PRE = re.compile(r"^(dev|alpha|a|beta|b|rc|patch|pl|p)\.?(\d*)$", re.IGNORECASE)


def _composer_key(v: str) -> tuple[Any, ...]:
    """Ordem do Composer: dev < alpha < beta < RC < estável < patch; sufixo numérico como número."""
    v = v.strip().lstrip("vV").split("+", 1)[0]
    core, _, pre = v.partition("-")
    nums = [int(m.group()) if (m := re.match(r"\d+", p)) else 0 for p in core.split(".")]
    nums += [0] * (4 - len(nums))
    if not pre:
        return (tuple(nums), 4, 0)
    match = _COMPOSER_PRE.match(pre)
    if not match:
        return (tuple(nums), 0, 0)            # desconhecido ⇒ abaixo de qualquer pré-release
    label, number = match.group(1).lower(), int(match.group(2) or 0)
    return (tuple(nums), 5 if label in ("patch", "pl", "p") else _COMPOSER_STABILITY[label], number)


def version_key(ecosystem: str, version: str) -> tuple[Any, ...]:
    """Chave ordenável. PyPI via PEP 440 (``packaging``); demais no formato semver-like."""
    if ecosystem == "PyPI":
        try:
            return (0, Version(version))
        except InvalidVersion:
            pass
    if ecosystem == "Packagist":
        return (2, _composer_key(version))
    return (1, _semverish_key(version))


def in_range(ecosystem: str, version: str, introduced: str | None, fixed: str | None) -> bool:
    """``introduced ≤ version < fixed`` (``introduced`` "0"/None = desde sempre; sem ``fixed`` = aberto)."""
    key = version_key(ecosystem, version)
    if introduced and introduced != "0" and key < version_key(ecosystem, introduced):
        return False
    return fixed is None or key < version_key(ecosystem, fixed)
