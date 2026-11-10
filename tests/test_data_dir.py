"""Diretório de dados da API (spec: .specs/features/dedup-and-test-isolation — ISO-01..02)."""
from __future__ import annotations

import os
import subprocess
import sys

from typer.testing import CliRunner

from auditor.api import store
from auditor.cli import app


# --- ISO-01: importar não cria diretório nenhum ------------------------------------------
def test_iso01_importing_store_and_app_creates_nothing(tmp_path):
    env = {k: v for k, v in os.environ.items() if k != "AUDITOR_DATA_DIR"}
    env["HOME"] = str(tmp_path)
    code = "import auditor.api.store, auditor.api.main"
    proc = subprocess.run([sys.executable, "-c", code], env=env, cwd=tmp_path,
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    assert not (tmp_path / ".config" / "auditor").exists()


# --- ISO-02: AUDITOR_DATA_DIR controla onde ficam os bancos ------------------------------
def test_iso02_data_dir_from_env(tmp_path, monkeypatch):
    target = tmp_path / "dados"
    monkeypatch.setenv("AUDITOR_DATA_DIR", str(target))

    assert store.meta_db_path() == target / "audits.sqlite"
    assert store.checkpoint_db_path() == target / "audits-checkpoints.sqlite"
    store.AuditStore()
    store.build_checkpointer()
    assert sorted(p.name for p in target.glob("*.sqlite")) == ["audits-checkpoints.sqlite",
                                                                "audits.sqlite"]


def test_iso02_default_is_home_config_and_not_created_eagerly(tmp_path, monkeypatch):
    monkeypatch.delenv("AUDITOR_DATA_DIR", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))

    assert store.meta_db_path() == tmp_path / ".config" / "auditor" / "audits.sqlite"
    assert not (tmp_path / ".config").exists()            # resolver o caminho não cria nada


def test_iso02_db_compact_default_follows_data_dir(tmp_path, monkeypatch):
    target = tmp_path / "dados"
    monkeypatch.setenv("AUDITOR_DATA_DIR", str(target))

    result = CliRunner().invoke(app, ["db", "compact"])

    assert result.exit_code == 0
    assert "Nada a compactar" in result.output
    assert str(target / "audits-checkpoints.sqlite") in result.output.replace("\n", "")
    assert not target.exists()                             # compact não cria o diretório
