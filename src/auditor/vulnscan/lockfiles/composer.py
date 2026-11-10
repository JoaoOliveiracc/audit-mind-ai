"""composer.lock (Packagist)."""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..models import Dependency, ParseResult
from . import register

ECO = "Packagist"
_PACKAGIST_NOTIFY = "https://packagist.org/downloads/"
_RELEASE = re.compile(r"^v?\d")


@register("composer.lock")
def parse_composer_lock(path: Path, rel: str, root: Path) -> ParseResult:
    result = ParseResult()
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("raiz não é um objeto")
        sections = [(data.get("packages") or [], False), (data.get("packages-dev") or [], True)]
        if not all(isinstance(pkgs, list) for pkgs, _ in sections):
            raise ValueError("'packages'/'packages-dev' inválidos")
    except (OSError, ValueError) as exc:
        result.errors.append(f"{rel}: lockfile inválido ({exc})")
        return result

    lines = text.splitlines()
    for packages, dev in sections:
        for pkg in packages:
            if not isinstance(pkg, dict) or not pkg.get("name") or not pkg.get("version"):
                continue
            name, raw_version = str(pkg["name"]), str(pkg["version"])
            is_release = bool(_RELEASE.match(raw_version))
            version = raw_version[1:] if raw_version[:1] in "vV" and is_release else raw_version
            # Só packagist.org garante pacote público: dist do GitHub vale também para repo privado.
            private = pkg.get("notification-url") != _PACKAGIST_NOTIFY or not is_release
            start = next((i for i, ln in enumerate(lines) if f'"name": "{name}"' in ln), 0)
            line = next((i + 1 for i in range(start, len(lines)) if '"version"' in lines[i]), start + 1)
            result.dependencies.append(Dependency(
                ecosystem=ECO, name=name, version=version, file=rel, line=line, dev=dev,
                private=private))
    return result
