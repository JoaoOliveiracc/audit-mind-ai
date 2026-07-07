"""Fábrica de modelos de linguagem — multi-provider via ``init_chat_model``.

Suporta qualquer provedor reconhecido pelo LangChain (Anthropic, OpenAI, Groq,
Google, Mistral, Ollama local, Bedrock, etc.). O provedor e o modelo são
configuráveis por ambiente (``AUDITOR_PROVIDER`` / ``AUDITOR_MODEL``) ou via CLI.
"""
from __future__ import annotations

import os
from functools import lru_cache

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

from .config import get_settings
from .logging_config import get_logger

logger = get_logger("llm")


class LLMConfigError(RuntimeError):
    """Erro de configuração do provedor de LLM (credencial ausente, pacote faltando…)."""


def _validate_credentials(settings) -> None:
    """Garante que a credencial exigida pelo provedor está presente no ambiente."""
    env_var = settings.credential_env_var()
    if env_var and not os.environ.get(env_var):
        raise LLMConfigError(
            f"Provedor '{settings.provider}' requer a variável de ambiente "
            f"'{env_var}', que não está definida. Configure-a no .env ou exporte-a."
        )


@lru_cache
def get_llm() -> BaseChatModel:
    """Cria (e memoiza) o chat model do provedor configurado.

    Levanta ``LLMConfigError`` com mensagem acionável quando a credencial ou o
    pacote de integração do provedor estão ausentes.
    """
    settings = get_settings()
    _validate_credentials(settings)

    kwargs: dict = {
        "model": settings.model,
        "model_provider": settings.provider,
        "temperature": settings.temperature,
        "max_tokens": settings.max_tokens,
    }
    if settings.base_url:
        kwargs["base_url"] = settings.base_url

    logger.info("Inicializando LLM: provider=%s model=%s", settings.provider, settings.model)
    try:
        return init_chat_model(**kwargs)
    except ImportError as exc:
        raise LLMConfigError(
            f"Pacote de integração ausente para o provedor '{settings.provider}'. "
            f"Instale com: pip install {settings.integration_package()}"
        ) from exc
    except Exception as exc:  # provedores lançam erros diversos de config
        raise LLMConfigError(
            f"Falha ao inicializar o provedor '{settings.provider}' "
            f"(modelo '{settings.model}'): {exc}"
        ) from exc


def reset_llm_cache() -> None:
    """Limpa o cache do modelo (usado quando o provedor/modelo muda em runtime)."""
    get_llm.cache_clear()
