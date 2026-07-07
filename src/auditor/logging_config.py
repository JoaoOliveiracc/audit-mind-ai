"""Configuração de logging estruturado do Audit Mind AI.

O logging é para **diagnóstico/observabilidade** (stderr, controlado por
``AUDITOR_LOG_LEVEL``); a UX interativa continua a cargo do ``rich.Console``.
``setup_logging`` é idempotente — chamá-la mais de uma vez não duplica handlers.
"""
from __future__ import annotations

import logging

_CONFIGURED = False
_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
_DATEFMT = "%H:%M:%S"


def setup_logging(level: str = "INFO") -> None:
    """Configura o logger raiz ``auditor`` uma única vez.

    Args:
        level: nível textual (DEBUG, INFO, WARNING, ERROR). Valores inválidos
            caem para INFO.
    """
    global _CONFIGURED
    logger = logging.getLogger("auditor")
    resolved = getattr(logging, str(level).upper(), logging.INFO)
    logger.setLevel(resolved)

    if _CONFIGURED:
        return

    handler = logging.StreamHandler()  # stderr
    handler.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATEFMT))
    logger.addHandler(handler)
    logger.propagate = False  # evita duplicar via root logger
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Retorna um logger filho de ``auditor`` (ex.: ``get_logger('llm')``)."""
    return logging.getLogger(f"auditor.{name}")
