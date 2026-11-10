"""Lockfiles Python (PyPI): poetry.lock, uv.lock, Pipfile.lock, requirements*.txt."""
from __future__ import annotations

import configparser
import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from ..models import Dependency, ParseResult
from ..versions import normalize_name
from . import register

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - coberto no CI 3.10
    import tomli as tomllib

ECO = "PyPI"
_PUBLIC_HOSTS = frozenset({"pypi.org", "files.pythonhosted.org"})
_DEV_FILE = re.compile(r"^(requirements-(dev|test).*|dev-requirements.*)\.txt$")
_PIN = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)(\[[^\]]*\])?\s*={2,3}\s*([^\s;#\\]+)")
_INDEX_OPT = re.compile(r"^\s*(-i|--index-url|--extra-index-url)(?:\s+|=)(\S+)")
_FIND_LINKS = re.compile(r"^\s*(-f|--find-links)(?:\s+|=)(\S+)")
_INCLUDE = re.compile(r"^\s*(-r|--requirement|-c|--constraint)(?:\s+|=)(\S+)")
_MAX_INCLUDE_DEPTH = 5


def _public_index(url: str | None) -> bool:
    if not url:
        return True  # sem índice explícito ⇒ PyPI
    parsed = urlparse(url)
    return parsed.scheme == "https" and parsed.hostname in _PUBLIC_HOSTS


_TOML_STR = re.compile(r'^(name|version) = "([^"]*)"')


def _package_version_lines(lines: list[str]) -> dict[tuple[str, str], int]:
    """``{(name, version): linha de "version = …"}`` por bloco ``[[package]]`` (uma passada).

    A chave inclui a versão: poetry/uv podem ter o mesmo pacote em várias versões (markers).
    """
    out: dict[tuple[str, str], int] = {}
    name: str | None = None
    version: tuple[str, int] | None = None
    for i, ln in enumerate(lines + ["[[package]]"]):
        if ln.startswith("[["):
            if name is not None and version is not None:
                out.setdefault((name, version[0]), version[1])
            name, version = None, None
            continue
        if ln.startswith("["):          # sub-tabela ([package.metadata] …): fim dos campos do bloco
            continue
        match = _TOML_STR.match(ln)
        if match and match.group(1) == "name" and name is None:
            name = match.group(2)
        elif match and match.group(1) == "version" and version is None:
            version = (match.group(2), i + 1)
    return out


def _load_toml(path: Path, rel: str) -> tuple[dict[str, Any] | None, list[str], str]:
    try:
        text = path.read_text(encoding="utf-8")
        return tomllib.loads(text), [], text
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return None, [f"{rel}: lockfile inválido ({exc})"], ""


# --- poetry.lock -------------------------------------------------------------------------
@register("poetry.lock")
def parse_poetry_lock(path: Path, rel: str, root: Path) -> ParseResult:
    data, errors, text = _load_toml(path, rel)
    if data is None:
        return ParseResult(errors=errors)
    version_line = _package_version_lines(text.splitlines())
    result = ParseResult()
    for pkg in data.get("package") or []:
        if not isinstance(pkg, dict) or not pkg.get("name") or not pkg.get("version"):
            continue
        groups = pkg.get("groups")
        dev = pkg.get("category") == "dev" or (isinstance(groups, list) and "main" not in groups)
        source = pkg.get("source") or {}
        private = bool(source) and not (source.get("type") in (None, "legacy")
                                        and _public_index(source.get("url")))
        result.dependencies.append(Dependency(
            ecosystem=ECO, name=normalize_name(ECO, str(pkg["name"])), version=str(pkg["version"]),
            file=rel, line=version_line.get((str(pkg["name"]), str(pkg["version"])), 1), dev=dev,
            private=private))
    return result


# --- uv.lock -----------------------------------------------------------------------------
@register("uv.lock")
def parse_uv_lock(path: Path, rel: str, root: Path) -> ParseResult:
    """``dev`` = citado só em ``dev-dependencies`` e em nenhum ``dependencies`` (diretas).

    Transitivas de dependências de dev não são marcadas: o uv.lock não as distingue sem
    percorrer o grafo — conservador (severidade real em vez de ``info``).
    """
    data, errors, text = _load_toml(path, rel)
    if data is None or not isinstance(data.get("package", []), list):
        return ParseResult(errors=errors or [f"{rel}: lockfile inválido ('package' não é lista)"])
    packages = [p for p in data.get("package") or [] if isinstance(p, dict)]
    runtime_names, dev_names = set(), set()
    for pkg in packages:
        for dep in pkg.get("dependencies") or []:
            runtime_names.add(normalize_name(ECO, str(dep.get("name", ""))))
        for group in (pkg.get("dev-dependencies") or {}).values():
            for dep in group or []:
                dev_names.add(normalize_name(ECO, str(dep.get("name", ""))))
    version_line = _package_version_lines(text.splitlines())
    result = ParseResult()
    for pkg in packages:
        if not pkg.get("name") or not pkg.get("version"):
            continue
        name = normalize_name(ECO, str(pkg["name"]))
        source = pkg.get("source") or {}
        registry = source.get("registry") if isinstance(source, dict) else None
        private = registry is None or not _public_index(str(registry))  # editable/git/path ⇒ privado
        result.dependencies.append(Dependency(
            ecosystem=ECO, name=name, version=str(pkg["version"]), file=rel,
            line=version_line.get((str(pkg["name"]), str(pkg["version"])), 1),
            dev=name in dev_names and name not in runtime_names, private=private))
    return result


# --- Pipfile.lock ------------------------------------------------------------------------
_JSON_KEY = re.compile(r'^(\s*)"([^"]+)":')


def _pipfile_version_lines(lines: list[str]) -> dict[tuple[str, str], int]:
    """``{(seção, nome): linha do "version"}`` respeitando a seção (mesmo nome em default e develop)."""
    out: dict[tuple[str, str], int] = {}
    section_indent: int | None = None
    section = current = None
    for i, ln in enumerate(lines):
        match = _JSON_KEY.match(ln)
        if not match:
            continue
        indent, key = len(match.group(1)), match.group(2)
        if section_indent is None or indent <= section_indent:
            section, section_indent, current = key, indent, None
        elif current is None or indent <= current[1]:
            current = (key, indent)
        elif key == "version" and section and (section, current[0]) not in out:
            out[(section, current[0])] = i + 1
    return out
@register("Pipfile.lock")
def parse_pipfile_lock(path: Path, rel: str, root: Path) -> ParseResult:
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("raiz não é um objeto")
    except (OSError, ValueError) as exc:
        return ParseResult(errors=[f"{rel}: lockfile inválido ({exc})"])
    sources = {s.get("name"): s.get("url") for s in (data.get("_meta") or {}).get("sources") or []
               if isinstance(s, dict)}
    default_index = next(iter(sources.values()), None)
    version_line = _pipfile_version_lines(text.splitlines())
    result = ParseResult()
    for section, dev in (("default", False), ("develop", True)):
        for raw_name, meta in (data.get(section) or {}).items():
            if not isinstance(meta, dict) or not str(meta.get("version", "")).startswith("=="):
                continue  # path/git/editable não têm versão fixa
            unknown_index = "index" in meta and meta["index"] not in sources   # dúvida ⇒ privado
            index_url = sources.get(meta["index"]) if "index" in meta else default_index
            private = unknown_index or any(k in meta for k in ("git", "path", "file", "editable")) \
                or not _public_index(index_url)
            line = version_line.get((section, raw_name), 1)
            result.dependencies.append(Dependency(
                ecosystem=ECO, name=normalize_name(ECO, raw_name),
                version=str(meta["version"])[2:], file=rel, line=line, dev=dev, private=private))
    return result


# --- requirements*.txt -------------------------------------------------------------------
def is_requirements_file(filename: str) -> bool:
    return (filename.startswith("requirements") or filename.endswith("requirements.txt")
            or filename.startswith("dev-requirements")) and filename.endswith(".txt")


def _declares_private_source(path: Path, root: Path, seen: set[Path], depth: int) -> bool:
    """Índice fora do PyPI ou ``--find-links`` aqui ou em ``-r``/``-c`` incluídos (dentro da raiz).

    Opções de índice do pip valem para toda a resolução, então um include basta para que a
    origem de cada pacote fique indeterminada (LOCK-03). Ciclos e caminhos fora da raiz são
    ignorados; profundidade limitada.
    """
    resolved = path.resolve()
    if resolved in seen or depth > _MAX_INCLUDE_DEPTH:
        return False
    seen.add(resolved)
    try:
        lines = resolved.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return False
    for raw in lines:
        index = _INDEX_OPT.match(raw)
        if (index and not _public_index(index.group(2))) or _FIND_LINKS.match(raw):
            return True
        include = _INCLUDE.match(raw)
        if include:
            target = (resolved.parent / include.group(2)).resolve()
            if (target == root or root in target.parents) and target.is_file() \
                    and _declares_private_source(target, root, seen, depth + 1):
                return True
    return False


_PIP_ENV_INDEXES = ("PIP_INDEX_URL", "PIP_EXTRA_INDEX_URL", "UV_INDEX_URL", "UV_EXTRA_INDEX_URL",
                    "UV_INDEX", "UV_DEFAULT_INDEX")
_PIP_ENV_LINKS = ("PIP_FIND_LINKS", "UV_FIND_LINKS")
_SYSTEM_PIP_CONFIGS = (Path("/etc/pip.conf"), Path("/etc/xdg/pip/pip.conf"))


def _pip_config_files() -> list[Path]:
    files = [Path(os.environ["PIP_CONFIG_FILE"])] if os.environ.get("PIP_CONFIG_FILE") else []
    try:
        home = Path.home()
        xdg = Path(os.environ.get("XDG_CONFIG_HOME") or home / ".config")
        files += [xdg / "pip" / "pip.conf", home / ".pip" / "pip.conf"]
    except RuntimeError:
        pass
    return files + list(_SYSTEM_PIP_CONFIGS)


def _urls(value: str) -> list[str]:
    return [u for u in re.split(r"[\s,]+", value) if u]


def global_pip_source_is_private() -> bool:
    """Índice/``find-links`` fora do PyPI no ambiente ou no ``pip.conf`` do usuário/sistema.

    Afeta todo ``requirements*.txt`` (que não registra a origem de cada pacote); poetry/uv/Pipfile
    gravam a origem no próprio lockfile. Config ilegível ⇒ dúvida ⇒ privado.
    """
    if any(os.environ.get(v) for v in _PIP_ENV_LINKS):
        return True
    for var in _PIP_ENV_INDEXES:
        if any(not _public_index(u) for u in _urls(os.environ.get(var, ""))):
            return True
    for conf in _pip_config_files():
        try:
            if not conf.is_file():
                continue
            parser = configparser.ConfigParser(interpolation=None)
            parser.read_string(conf.read_text(encoding="utf-8", errors="replace"))
        except (OSError, configparser.Error):
            return True
        for section in parser.sections():
            if parser.get(section, "find-links", fallback=""):
                return True
            for key in ("index-url", "extra-index-url"):
                if any(not _public_index(u) for u in _urls(parser.get(section, key, fallback=""))):
                    return True
    return False


def parse_requirements(path: Path, rel: str, root: Path) -> ParseResult:
    """Só pins exatos ``nome==versão``. Índice fora do PyPI ⇒ o arquivo inteiro é pulado (LOCK-03)."""
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError as exc:
        return ParseResult(errors=[f"{rel}: ilegível ({exc})"])
    if global_pip_source_is_private() or _declares_private_source(path, root.resolve(), set(), 0):
        return ParseResult(skipped_files=[rel])
    dev = bool(_DEV_FILE.match(Path(rel).name))
    result = ParseResult()
    for number, raw in enumerate(lines, start=1):
        line = raw.split("#", 1)[0] if not raw.lstrip().startswith("#") else ""
        pin = _PIN.match(line)
        if pin:
            result.dependencies.append(Dependency(
                ecosystem=ECO, name=normalize_name(ECO, pin.group(1)), version=pin.group(3),
                file=rel, line=number, dev=dev))
    return result
