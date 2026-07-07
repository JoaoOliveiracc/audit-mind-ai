"""Fábrica de modelos de linguagem — multi-provider via ``init_chat_model``.

Suporta qualquer provedor reconhecido pelo LangChain (Anthropic, OpenAI, Groq,
Google, Mistral, Ollama local, Bedrock, etc.). O provedor e o modelo são
configuráveis por ambiente (``AUDITOR_PROVIDER`` / ``AUDITOR_MODEL``), via CLI ou
**por auditoria** (override passado a ``get_llm(provider, model)``).

O modelo é memoizado por ``(provider, model, ...)`` — não há singleton global
mutável, então auditorias concorrentes com provedores distintos não colidem.
"""
from __future__ import annotations

import os
from functools import lru_cache

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

from .config import PROVIDER_ENV_VAR, PROVIDER_PACKAGE, get_settings
from .logging_config import get_logger

logger = get_logger("llm")


class LLMConfigError(RuntimeError):
    """Erro de configuração do provedor de LLM (credencial ausente, pacote faltando…)."""


def _validate_credentials(provider: str) -> None:
    """Garante que a credencial exigida pelo provedor está presente no ambiente."""
    env_var = PROVIDER_ENV_VAR.get(provider)
    if env_var and not os.environ.get(env_var):
        raise LLMConfigError(
            f"Provedor '{provider}' requer a variável de ambiente "
            f"'{env_var}', que não está definida. Configure-a no .env ou exporte-a."
        )


@lru_cache
def _build_llm(
    provider: str, model: str, temperature: float, max_tokens: int, base_url: str
) -> BaseChatModel:
    """Cria (e memoiza) o chat model, chaveado por provedor/modelo/params.

    Levanta ``LLMConfigError`` com mensagem acionável quando a credencial ou o
    pacote de integração do provedor estão ausentes.
    """
    _validate_credentials(provider)

    kwargs: dict = {
        "model": model,
        "model_provider": provider,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if base_url:
        kwargs["base_url"] = base_url

    logger.info("Inicializando LLM: provider=%s model=%s", provider, model)
    try:
        return init_chat_model(**kwargs)
    except ImportError as exc:
        pkg = PROVIDER_PACKAGE.get(provider, f"langchain-{provider}")
        raise LLMConfigError(
            f"Pacote de integração ausente para o provedor '{provider}'. "
            f"Instale com: pip install {pkg}"
        ) from exc
    except Exception as exc:  # provedores lançam erros diversos de config
        raise LLMConfigError(
            f"Falha ao inicializar o provedor '{provider}' (modelo '{model}'): {exc}"
        ) from exc


def get_llm(provider: str | None = None, model: str | None = None) -> BaseChatModel:
    """Retorna o chat model configurado.

    Sem argumentos, usa provedor/modelo das configurações globais. Com ``provider``
    / ``model`` explícitos (override por auditoria), constrói/reaproveita o modelo
    correspondente — sem mutar estado global do processo.
    """
    settings = get_settings()
    return _build_llm(
        provider or settings.provider,
        model or settings.model,
        settings.temperature,
        settings.max_tokens,
        settings.base_url or "",
    )


def reset_llm_cache() -> None:
    """Limpa o cache de modelos (usado em testes ou reconfiguração)."""
    _build_llm.cache_clear()
