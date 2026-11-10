"""Runtime declarado no projeto (RT-01) e sua classificação por runtime (RT-02, puro).

Ciclo e exatidão dependem do runtime: Node usa o major como ciclo (``20``) e considera exata
``major.minor[.patch]``; PHP e Python usam ``major.minor`` como ciclo e exata ``major.minor.patch``.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from .models import RuntimeDecl

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - coberto no CI 3.10
    import tomli as tomllib

_IMAGES = {"node": "nodejs", "php": "php", "python": "python"}
_PURE = re.compile(r"^\d+(\.\d+){0,2}$")
_TOKEN = re.compile(r"(!=|<=?|>=?|\^|~=?|==|=)?\s*v?(\d+)(?:\.(\d+|[xX*]))?(?:\.(\d+|[xX*]))?")
_LEADING_VERSION = re.compile(r"^\d+(\.\d+)*")


@dataclass(frozen=True)
class Classified:
    kind: str                 # "exact" | "cycle" | "range" | "unknown"
    cycle: str | None
    exact: str | None


_UNKNOWN = Classified("unknown", None, None)


def _cycle(product: str, major: str, minor: str | None) -> str:
    if product == "nodejs":
        return major
    return f"{major}.{minor if minor and minor.isdigit() else '0'}"


def classify(product: str, value: str) -> Classified:
    """Classifica uma declaração. Tags sem versão, variáveis e ``*`` ⇒ ``unknown`` (RT-04)."""
    v = value.strip()
    if not v or "${" in v or v in ("*", "x", "X") or not re.search(r"\d", v):
        return _UNKNOWN
    bare = v[1:] if v[:1] in "vV" and v[1:2].isdigit() else v
    if _PURE.match(bare):
        parts = bare.split(".")
        if product == "nodejs":
            return Classified("cycle", parts[0], None) if len(parts) == 1 else \
                Classified("exact", parts[0], bare)
        if len(parts) == 1:
            return _UNKNOWN            # "python:3" / "php:8": ciclo indeterminado
        cycle = f"{parts[0]}.{parts[1]}"
        return Classified("cycle", cycle, None) if len(parts) == 2 else Classified("exact", cycle, bare)
    if not re.match(r"^[\s<>=!^~|vV0-9.xX*,-]+$", v):
        return _UNKNOWN                # "pypy3.10", "lts/iron", "20-alpine" sem extração prévia
    lower_bounds = []
    for alternative in re.split(r"\|\|", v):
        for op, major, minor, _patch in _TOKEN.findall(alternative):
            if not op.startswith(("<", "!")):          # "<" é teto; "!=" exclui, não limita
                lower_bounds.append((int(major), int(minor) if minor.isdigit() else 0, major, minor))
    if not lower_bounds:
        return _UNKNOWN
    _, _, major, minor = min(lower_bounds)
    if product != "nodejs" and minor and not minor.isdigit():
        return _UNKNOWN    # "3.x"/"8.x" (curinga): mínimo indeterminado; ">=8" (ausente) = 8.0
    return Classified("range", _cycle(product, major, minor), None)


# --- detecção por arquivo ----------------------------------------------------------------
def _is_dockerfile(name: str) -> bool:
    lower = name.lower()
    return lower == "dockerfile" or lower.startswith("dockerfile.") or lower.endswith(".dockerfile")


def _line_after(lines: list[str], anchor: str, needle: str) -> int | None:
    start = next((i for i, ln in enumerate(lines) if anchor in ln), None)
    if start is None:
        return None
    return next((i + 1 for i in range(start, len(lines)) if needle in lines[i]), None)


def _version_file(product: str, rel: str, lines: list[str]) -> list[RuntimeDecl]:
    for number, raw in enumerate(lines, start=1):
        line = raw.strip()
        if line and not line.startswith("#"):
            value = line[1:] if line[:1] in "vV" and line[1:2].isdigit() else line
            return [RuntimeDecl(product, value, rel, number, line)]
    return []


def _json_field(product: str, rel: str, text: str, section: str, key: str) -> list[RuntimeDecl]:
    try:
        data = json.loads(text)
        value = data.get(section, {}).get(key) if isinstance(data, dict) else None
    except (ValueError, AttributeError):
        return []
    if not isinstance(value, str):
        return []
    lines = text.splitlines()
    number = _line_after(lines, f'"{section}"', f'"{key}"')
    if number is None:
        return []
    return [RuntimeDecl(product, value, rel, number, lines[number - 1].strip())]


def _pyproject(rel: str, text: str) -> list[RuntimeDecl]:
    try:
        value = (tomllib.loads(text).get("project") or {}).get("requires-python")
    except tomllib.TOMLDecodeError:
        return []
    if not isinstance(value, str):
        return []
    lines = text.splitlines()
    number = next((i + 1 for i, ln in enumerate(lines) if ln.strip().startswith("requires-python")), None)
    return [RuntimeDecl("python", value, rel, number, lines[number - 1].strip())] if number else []


def _dockerfile(rel: str, lines: list[str]) -> list[RuntimeDecl]:
    decls = []
    for number, raw in enumerate(lines, start=1):
        tokens = raw.split()
        if not tokens or tokens[0].upper() != "FROM":
            continue
        image = next((t for t in tokens[1:] if not t.startswith("--")), "")
        image = image.split("@", 1)[0]                       # digest
        repo, _, tag = image.rpartition(":") if ":" in image.rsplit("/", 1)[-1] else (image, "", "")
        name = repo.rsplit("/", 1)[-1]                       # docker.io/library/node → node
        if name not in _IMAGES:
            continue
        leading = _LEADING_VERSION.match(tag)
        value = leading.group() if leading else (tag or "latest")
        decls.append(RuntimeDecl(_IMAGES[name], value, rel, number, raw.strip()))
    return decls


def detect_in_file(path: Path, rel: str) -> list[RuntimeDecl]:
    """Declarações de runtime de um arquivo; cada uma independente (RT-05). Nunca lança."""
    name = path.name
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    lines = text.splitlines()
    if name in (".nvmrc", ".node-version"):
        return _version_file("nodejs", rel, lines)
    if name == ".python-version":
        return _version_file("python", rel, lines)
    if name == "package.json":
        return _json_field("nodejs", rel, text, "engines", "node")
    if name == "composer.json":
        return _json_field("php", rel, text, "require", "php")
    if name == "pyproject.toml":
        return _pyproject(rel, text)
    if _is_dockerfile(name):
        return _dockerfile(rel, lines)
    return []
