"""Aplicação FastAPI do Audit Mind AI (modo local/desktop)."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .. import __version__
from ..config import get_settings
from ..logging_config import setup_logging
from .routes import router

setup_logging(get_settings().log_level)

app = FastAPI(
    title="Audit Mind AI API",
    version=__version__,
    description="API local para o agent de auditoria (frontend Vite/React consome esta API).",
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

app.include_router(router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": __version__}
