"""Lockfiles npm: package-lock.json (v2/v3), yarn.lock (v1 e berry), pnpm-lock.yaml (v6/v9)."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from ..models import Dependency, ParseResult
from . import register
from ._lines import NextLine, first_index
from .registry_config import RegistryConfig, is_public_npm_url, load_registry_config

ECO = "npm"


def _split_name_version(spec: str) -> tuple[str, str] | None:
    """``@scope/pkg@1.2.3`` → (``@scope/pkg``, ``1.2.3``).

    Nomes npm não contêm ``@`` (exceto o inicial do escopo), então o separador é o primeiro
    ``@`` após a posição 0 — vale também para ``x@1.0.0_peer@2`` (pnpm v6) e ``x@patch:x@npm…``.
    """
    idx = spec.find("@", 1)
    if idx <= 0:
        return None
    return spec[:idx], spec[idx + 1:]


def _private(cfg: RegistryConfig, name: str, resolved: str | None) -> bool:
    """Dúvida ⇒ privado: sem ``resolved``, host não público ou escopo mapeado (LOCK-03)."""
    return cfg.is_private(name) or not resolved or not is_public_npm_url(resolved)


def _json_object_key(line: str) -> str | None:
    """``    "node_modules/x": {`` → ``node_modules/x``."""
    s = line.strip()
    if s.startswith('"') and s.endswith("{"):
        end = s.find('"', 1)
        return s[1:end] if end > 0 else None
    return None


# --- package-lock.json -------------------------------------------------------------------
@register("package-lock.json", "npm-shrinkwrap.json")
def parse_package_lock(path: Path, rel: str, root: Path) -> ParseResult:
    result = ParseResult()
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("raiz não é um objeto")
        if data.get("lockfileVersion", 1) < 2:
            result.errors.append(f"{rel}: lockfileVersion 1 não suportado (regenere com npm ≥ 7)")
            return result
        packages = data.get("packages")
        if not isinstance(packages, dict):
            raise ValueError("'packages' ausente ou inválido")
    except (OSError, ValueError, TypeError) as exc:
        result.errors.append(f"{rel}: lockfile inválido ({exc})")
        return result

    cfg = load_registry_config(root, path.parent)
    lines = text.splitlines()
    key_line, version_line = first_index(lines, _json_object_key), NextLine(lines, '"version"')
    for key, meta in packages.items():
        if not key or not isinstance(meta, dict) or "node_modules/" not in key:
            continue
        # alias ("node_modules/my-lodash": {"name": "lodash"}): consulta o pacote REAL
        name = str(meta.get("name") or key.rsplit("node_modules/", 1)[1])
        version = meta.get("version")
        if not version or meta.get("link"):
            continue  # workspace/link: não é pacote do registro
        result.dependencies.append(Dependency(
            ecosystem=ECO, name=name, version=str(version), file=rel,
            line=version_line.after(key_line.get(key, 0)),
            dev=bool(meta.get("dev")), private=_private(cfg, name, meta.get("resolved")),
        ))
    return result


# --- yarn.lock ---------------------------------------------------------------------------
@register("yarn.lock")
def parse_yarn_lock(path: Path, rel: str, root: Path) -> ParseResult:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return ParseResult(errors=[f"{rel}: ilegível ({exc})"])
    cfg = load_registry_config(root, path.parent)
    try:
        if re.search(r"^__metadata:", text, re.M):
            return _parse_yarn_berry(text, rel, cfg)
        return _parse_yarn_v1(text, rel, cfg)
    except (ValueError, yaml.YAMLError) as exc:
        return ParseResult(errors=[f"{rel}: lockfile inválido ({exc})"])


def _parse_yarn_v1(text: str, rel: str, cfg: RegistryConfig) -> ParseResult:
    result = ParseResult()
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        header = lines[i]
        if not header or header.startswith(("#", " ")) or not header.rstrip().endswith(":"):
            i += 1
            continue
        first_spec = header.rstrip()[:-1].split(",")[0].strip().strip('"')
        parsed = _split_name_version(first_spec)
        if parsed and parsed[1].startswith("npm:"):       # alias "my-lodash@npm:lodash@^4"
            parsed = _split_name_version(parsed[1][4:]) or parsed
        version = resolved = None
        version_line = i + 1
        j = i + 1
        while j < len(lines) and lines[j].startswith(" "):
            body = lines[j].strip()
            if body.startswith("version "):
                version, version_line = body.split(" ", 1)[1].strip('"'), j + 1
            elif body.startswith("resolved "):
                resolved = body.split(" ", 1)[1].strip('"')
            j += 1
        if parsed and version:
            name = parsed[0]
            result.dependencies.append(Dependency(
                ecosystem=ECO, name=name, version=version, file=rel, line=version_line,
                private=_private(cfg, name, resolved)))
        i = j
    return result


def _parse_yarn_berry(text: str, rel: str, cfg: RegistryConfig) -> ParseResult:
    result = ParseResult()
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError("raiz não é um mapa")
    lines = text.splitlines()
    key_line = first_index(lines, lambda ln: None if not ln or ln[0] in " #" else ln.rstrip().rstrip(":").strip('"'))
    version_line = NextLine(lines, "version:")
    for key, meta in data.items():
        if key == "__metadata" or not isinstance(meta, dict):
            continue
        resolution = str(meta.get("resolution") or "")
        parsed = _split_name_version(resolution)
        version = meta.get("version")
        if not parsed or version is None:
            continue
        base_name, ref = parsed                     # "lodash@npm:4.17.15" → ("lodash", "npm:4.17.15")
        is_registry = ref.split(":", 1)[0] == "npm"   # workspace:/patch:/git:/file:/link: ⇒ privado
        result.dependencies.append(Dependency(
            ecosystem=ECO, name=base_name, version=str(version), file=rel,
            line=version_line.after(key_line.get(str(key), 0)),
            private=(not is_registry) or cfg.is_private(base_name)))
    return result


# --- pnpm-lock.yaml ----------------------------------------------------------------------
@register("pnpm-lock.yaml")
def parse_pnpm_lock(path: Path, rel: str, root: Path) -> ParseResult:
    result = ParseResult()
    try:
        text = path.read_text(encoding="utf-8")
        data: Any = yaml.safe_load(text)
        packages = data.get("packages") if isinstance(data, dict) else None
        if not isinstance(packages, dict):
            raise ValueError("'packages' ausente ou inválido")
    except (OSError, ValueError, AttributeError, yaml.YAMLError) as exc:
        result.errors.append(f"{rel}: lockfile inválido ({exc})")
        return result

    cfg = load_registry_config(root, path.parent)
    lines = text.splitlines()
    pkg_start = next((i for i, ln in enumerate(lines) if ln.startswith("packages:")), 0)
    try:
        legacy_v5 = float(str(data.get("lockfileVersion", "9")).strip("'\"")) < 6
    except ValueError:
        legacy_v5 = False
    unrecognized: list[str] = []
    key_line = first_index(lines, lambda ln: ln.strip().rstrip(":").strip("'\"") or None, pkg_start)
    for raw_key, meta in packages.items():
        key = str(raw_key).lstrip("/").split("(", 1)[0]
        if legacy_v5 and "/" in key:      # v5: "/lodash/4.17.21", "/@types/node/18.0.0"
            name_part, _, version_part = key.rpartition("/")
            parsed = (name_part, version_part) if name_part and version_part[:1].isdigit() else None
        else:
            parsed = _split_name_version(key)
        if not parsed:
            unrecognized.append(str(raw_key))
            continue
        name, version = parsed[0], parsed[1].split("_", 1)[0]   # v5/v6: sufixo "_peer@x"
        meta = meta if isinstance(meta, dict) else {}
        resolution = meta.get("resolution") or {}
        from_registry = isinstance(resolution, dict) and "integrity" in resolution \
            and "tarball" not in resolution and "type" not in resolution
        line = key_line.get(str(raw_key), pkg_start) + 1
        result.dependencies.append(Dependency(
            ecosystem=ECO, name=name, version=version, file=rel, line=line,
            dev=meta.get("dev") is True, private=(not from_registry) or cfg.is_private(name)))
    if unrecognized:   # nunca "limpo" em silêncio: a varredura fica marcada como incompleta
        result.errors.append(f"{rel}: {len(unrecognized)} entrada(s) não reconhecida(s) "
                             f"(ex.: {unrecognized[0]})")
    return result
