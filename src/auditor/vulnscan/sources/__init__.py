"""Gateways HTTP (OSV.dev, endoflife.date) com allowlist de host e limites (AD-003)."""
from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

import httpx

MAX_RESPONSE_BYTES = 5 * 1024 * 1024
TIMEOUT_SECONDS = 15.0


class SourceError(Exception):
    """Falha de uma fonte externa (HTTP, tamanho, JSON) — vira erro registrado, nunca exceção."""


def checked_client(http: httpx.Client | None, base_url: str) -> httpx.Client:
    """Cliente com ``base_url`` igual ao host permitido (HTTPS). Injetável para testes."""
    client = http or httpx.Client(base_url=base_url, timeout=TIMEOUT_SECONDS)
    allowed, actual = urlparse(base_url), urlparse(str(client.base_url))
    if actual.scheme != "https" or actual.hostname != allowed.hostname:
        raise ValueError(f"host não permitido para esta fonte: {client.base_url}")
    return client


def get_json(http: httpx.Client, method: str, path: str, payload: Any = None) -> Any:
    """Requisição relativa ao ``base_url`` com corpo lido em streaming até 5 MB."""
    try:
        with http.stream(method, path, json=payload) as response:
            response.raise_for_status()
            body = bytearray()
            for chunk in response.iter_bytes():
                body.extend(chunk)
                if len(body) > MAX_RESPONSE_BYTES:
                    raise SourceError(f"{path}: resposta excede 5 MB")
        return json.loads(bytes(body))
    except SourceError:
        raise
    except (httpx.HTTPError, ValueError) as exc:
        raise SourceError(f"{path}: {exc.__class__.__name__}: {exc}") from exc
