"""Configuração central do agent, carregada de variáveis de ambiente / .env."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Carrega credenciais/config para o ambiente do processo (sem sobrescrever
# variáveis já definidas → a primeira fonte vence). Ordem de precedência:
#   1. Variáveis já exportadas no shell
#   2. .env do diretório atual (fluxo de desenvolvimento dentro do projeto)
#   3. ~/.config/auditor/.env (config de usuário, para rodar em qualquer terminal)
# Assim, as SDKs de cada provedor leem suas chaves (DEEPSEEK_API_KEY, etc.) de os.environ.
load_dotenv(override=False)
_USER_ENV = Path.home() / ".config" / "auditor" / ".env"
if _USER_ENV.is_file():
    load_dotenv(_USER_ENV, override=False)

# Provedor -> variável de ambiente da credencial (None = não requer chave, ex.: local).
PROVIDER_ENV_VAR: dict[str, str | None] = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "azure_openai": "AZURE_OPENAI_API_KEY",
    "google_genai": "GOOGLE_API_KEY",
    "google_vertexai": None,  # usa credenciais do gcloud
    "groq": "GROQ_API_KEY",
    "mistralai": "MISTRAL_API_KEY",
    "cohere": "COHERE_API_KEY",
    "together": "TOGETHER_API_KEY",
    "fireworks": "FIREWORKS_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "bedrock": None,  # usa credenciais AWS
    "ollama": None,  # local
}

# Provedor -> pacote de integração necessário (para mensagem de erro amigável).
PROVIDER_PACKAGE: dict[str, str] = {
    "anthropic": "langchain-anthropic",
    "openai": "langchain-openai",
    "azure_openai": "langchain-openai",
    "google_genai": "langchain-google-genai",
    "google_vertexai": "langchain-google-vertexai",
    "groq": "langchain-groq",
    "mistralai": "langchain-mistralai",
    "cohere": "langchain-cohere",
    "together": "langchain-together",
    "fireworks": "langchain-fireworks",
    "deepseek": "langchain-deepseek",
    "bedrock": "langchain-aws",
    "ollama": "langchain-ollama",
}


class Settings(BaseSettings):
    """Configurações globais do Audit Mind AI.

    Todos os valores podem ser sobrescritos por variáveis de ambiente com o
    prefixo ``AUDITOR_`` (exceto ``ANTHROPIC_API_KEY``, que segue o padrão da SDK).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Provedor / Modelo
    provider: str = Field(default="anthropic", alias="AUDITOR_PROVIDER")
    model: str = Field(default="claude-sonnet-4-5", alias="AUDITOR_MODEL")
    temperature: float = Field(default=0.0, alias="AUDITOR_TEMPERATURE")
    max_tokens: int = Field(default=8000, alias="AUDITOR_MAX_TOKENS")
    # Endpoint customizado (Ollama, gateways compatíveis com OpenAI, etc.)
    base_url: str = Field(default="", alias="AUDITOR_BASE_URL")

    # Credencial legada (mantida para compatibilidade; as chaves dos demais
    # provedores são lidas diretamente do ambiente pelas respectivas SDKs).
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")

    def credential_env_var(self) -> str | None:
        """Nome da variável de ambiente da credencial exigida pelo provedor atual."""
        return PROVIDER_ENV_VAR.get(self.provider, None)

    def integration_package(self) -> str:
        """Pacote de integração LangChain necessário para o provedor atual."""
        return PROVIDER_PACKAGE.get(self.provider, f"langchain-{self.provider}")

    # Limites de varredura
    max_file_bytes: int = Field(default=200_000, alias="AUDITOR_MAX_FILE_BYTES")
    max_files: int = Field(default=5000, alias="AUDITOR_MAX_FILES")
    max_search_results: int = Field(default=50, alias="AUDITOR_MAX_SEARCH_RESULTS")
    max_investigator_steps: int = Field(default=80, alias="AUDITOR_MAX_INVESTIGATOR_STEPS")

    # Comportamento
    log_level: str = Field(default="INFO", alias="AUDITOR_LOG_LEVEL")
    output_dir: str = Field(default="./audit-reports", alias="AUDITOR_OUTPUT_DIR")
    # Verificação determinística de evidência (descarta achados não-substanciados)
    verify_findings: bool = Field(default=True, alias="AUDITOR_VERIFY_EVIDENCE")

    # Diretórios ignorados na varredura
    ignore_dirs: tuple[str, ...] = (
        ".git", ".hg", ".svn", "node_modules", "venv", ".venv", "env",
        "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache",
        "dist", "build", "target", "out", ".next", ".nuxt", "vendor",
        "coverage", ".idea", ".vscode", "bin", "obj", ".gradle",
    )

    # Extensões tratadas como binárias/irrelevantes para leitura
    binary_extensions: tuple[str, ...] = (
        ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".pdf", ".zip",
        ".gz", ".tar", ".jar", ".war", ".class", ".exe", ".dll", ".so",
        ".dylib", ".woff", ".woff2", ".ttf", ".eot", ".mp4", ".mp3", ".mov",
        ".lock", ".bin", ".wasm",
    )


@lru_cache
def get_settings() -> Settings:
    """Retorna a instância singleton de configurações."""
    return Settings()
