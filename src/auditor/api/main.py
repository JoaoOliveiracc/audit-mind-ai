"""Aplicação FastAPI do Auditor-IA (modo local/desktop)."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .. import __version__
from .routes import router

app = FastAPI(
    title="Auditor-IA API",
    version=__version__,
    description="API local para o agent de auditoria (React/Next consome esta API).",
)

# CORS restrito ao frontend local.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3020",
        "http://127.0.0.1:3020",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": __version__}
