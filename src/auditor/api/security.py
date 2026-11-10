"""Allowlist de ``Host`` para a API local (defesa contra DNS rebinding — AD-002).

CORS não protege contra DNS rebinding: a página maliciosa passa a ser "same-origin"
com a API, mas o header ``Host`` continua sendo o domínio do atacante. Rejeitar
qualquer ``Host`` que não seja de loopback fecha esse vetor.

Middleware próprio porque o ``TrustedHostMiddleware`` do Starlette extrai o host com
``split(":")[0]``, o que quebra IPv6 (``[::1]:8020`` → ``[``).
"""
from __future__ import annotations

import re

from starlette.datastructures import Headers
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Receive, Scope, Send

DEFAULT_ALLOWED_HOSTS = frozenset({"localhost", "127.0.0.1", "[::1]"})

# host (nome/IPv4 ou IPv6 entre colchetes) + porta numérica opcional — nada mais.
_HOST_RE = re.compile(r"^(\[[0-9a-f:.]+\]|[a-z0-9.-]+)(?::\d{1,5})?$")


def parse_host(header: str) -> str:
    """Extrai o host (sem porta, minúsculo) de um header ``Host``; IPv6 entre colchetes.

    Formatos ambíguos (``localhost:evil``, ``[::1]evil``) retornam ``""`` (rejeitados).
    """
    match = _HOST_RE.match(header.strip().lower())
    return match.group(1) if match else ""


def allowed_hosts(extra: str = "") -> frozenset[str]:
    """Hosts de loopback + extras (lista separada por vírgula, ex.: ``AUDITOR_ALLOWED_HOSTS``)."""
    # Extras inválidos viram "" no parse — nunca podem entrar (abririam Host vazio/malformado).
    extras = {host for host in (parse_host(h) for h in extra.split(",")) if host}
    return DEFAULT_ALLOWED_HOSTS | frozenset(extras)


class LocalHostOnlyMiddleware:
    """Responde ``400`` a requisições HTTP/WebSocket cujo ``Host`` não está na allowlist."""

    def __init__(self, app: ASGIApp, allowed: frozenset[str] = DEFAULT_ALLOWED_HOSTS) -> None:
        self.app = app
        self.allowed = allowed

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket"):
            values = Headers(scope=scope).getlist("host")
            host = parse_host(values[0]) if len(values) == 1 else ""  # 0 ou duplicado → rejeita
            if host not in self.allowed:
                response = PlainTextResponse("Host não permitido.", status_code=400)
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)
