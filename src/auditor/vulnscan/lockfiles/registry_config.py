"""Configuração de registro npm do projeto (.npmrc, .yarnrc.yml) — LOCK-03.

Necessária porque os lockfiles do yarn berry e do pnpm não guardam o host do registro: um
escopo (ou o registro padrão) apontado para um host privado torna os pacotes privados.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import yaml

PUBLIC_NPM_HOSTS = frozenset({"registry.npmjs.org", "registry.yarnpkg.com"})


def is_public_npm_url(url: str) -> bool:
    parsed = urlparse(url.strip())
    return parsed.scheme == "https" and parsed.hostname in PUBLIC_NPM_HOSTS


@dataclass
class RegistryConfig:
    default_private: bool = False
    private_scopes: set[str] = field(default_factory=set)   # sem o "@"

    def is_private(self, name: str) -> bool:
        if self.default_private:
            return True
        return name.startswith("@") and name[1:].split("/", 1)[0] in self.private_scopes


def _apply(cfg: RegistryConfig, scope: str | None, url: str) -> None:
    if is_public_npm_url(url):
        return
    if scope is None:
        cfg.default_private = True
    else:
        cfg.private_scopes.add(scope.lstrip("@"))


def load_registry_config(*dirs: Path) -> RegistryConfig:
    """Lê ``.npmrc`` e ``.yarnrc.yml`` de cada diretório (raiz e pasta do lockfile)."""
    cfg = RegistryConfig()
    for d in dict.fromkeys(dirs):
        for raw in _read(d / ".npmrc").splitlines():
            line = raw.strip()
            if not line or line.startswith(("#", ";")) or "=" not in line:
                continue
            key, value = (s.strip() for s in line.split("=", 1))
            if key == "registry":
                _apply(cfg, None, value)
            elif key.endswith(":registry") and key.startswith("@"):
                _apply(cfg, key[: -len(":registry")], value)
        try:
            data = yaml.safe_load(_read(d / ".yarnrc.yml")) or {}
        except yaml.YAMLError:
            data = {}
        if not isinstance(data, dict):
            continue
        if data.get("npmRegistryServer"):
            _apply(cfg, None, str(data["npmRegistryServer"]))
        scopes = data.get("npmScopes")
        for scope, conf in (scopes.items() if isinstance(scopes, dict) else []):
            if isinstance(conf, dict) and conf.get("npmRegistryServer"):
                _apply(cfg, str(scope), str(conf["npmRegistryServer"]))
    return cfg


def _read(path: Path) -> str:
    """Conteúdo tolerante (nunca lança): ausente/ilegível ⇒ vazio; bytes inválidos substituídos."""
    try:
        return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
    except OSError:
        return ""
