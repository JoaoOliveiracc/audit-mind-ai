"""Aplicação FastAPI do Audit Mind AI (modo local/desktop)."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .. import __version__
from ..config import get_settings
from ..logging_config import get_logger, setup_logging
from .deps import get_store
from .routes import router
from .security import LocalHostOnlyMiddleware, allowed_hosts

setup_logging(get_settings().log_level)
logger = get_logger("api")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Na subida: nenhum runner sobrevive a um restart — órfãs viram ``interrupted``
    (retomáveis via ``POST /audits/{id}/resume``)."""
    changed = get_store().mark_orphans_interrupted()
    if changed:
        logger.info("%d auditoria(s) órfã(s) marcada(s) como interrompida(s)", changed)
    yield

app = FastAPI(
    title="Audit Mind AI API",
    version=__version__,
    description="API local para o agent de auditoria (frontend Vite/React consome esta API).",
    lifespan=lifespan,
)

# CORS restrito ao frontend local (Vite dev server em :5173). O proxy do Vite
# torna as requisições same-origin em dev; estas origens cobrem o acesso direto.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Adicionado por último → camada mais externa: rejeita Host não-local antes de tudo
# (inclusive preflight CORS). Defesa contra DNS rebinding (AD-002).
app.add_middleware(
    LocalHostOnlyMiddleware, allowed=allowed_hosts(get_settings().allowed_hosts)
)

app.include_router(router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": __version__}
