"""Isolamento global dos testes: nenhum teste toca o ``~/.config/auditor`` real (ISO-03).

1. ``HOME`` aponta para um diretório temporário JÁ NO IMPORT deste arquivo — antes de os
   módulos do ``auditor`` serem carregados — então nem o ``~/.config/auditor/.env`` real nem
   os bancos reais entram nos testes.
2. Cada teste recebe um ``AUDITOR_DATA_DIR`` próprio e singletons da API recriados.
3. Ao fim da sessão, falha se algo tiver criado ``$HOME/.config/auditor`` (vazamento).
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

_FAKE_HOME = Path(tempfile.mkdtemp(prefix="auditor-test-home-"))
os.environ["HOME"] = str(_FAKE_HOME)


@pytest.fixture(autouse=True, scope="session")
def _no_leak_into_home():
    yield
    leaked = _FAKE_HOME / ".config" / "auditor"
    if leaked.exists():
        pytest.fail(f"teste vazou dados para $HOME/.config/auditor ({leaked}) — use AUDITOR_DATA_DIR")


@pytest.fixture(autouse=True)
def _isolated_data_dir(tmp_path_factory, monkeypatch):
    """Cada teste usa um AUDITOR_DATA_DIR temporário e singletons da API recriados."""
    monkeypatch.setenv("AUDITOR_DATA_DIR", str(tmp_path_factory.mktemp("auditor-data")))
    try:
        from auditor.api import deps
    except ImportError:  # extras da API ausentes
        yield
        return
    caches = (deps.get_store, deps.get_checkpointer, deps.get_graph)
    for cached in caches:
        cached.cache_clear()
    yield
    for cached in caches:
        cached.cache_clear()
