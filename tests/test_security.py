"""Allowlist de Host contra DNS rebinding (spec: .specs/features/api-hardening — HOST-01..04)."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auditor.api import routes
from auditor.api.main import app
from auditor.api.security import LocalHostOnlyMiddleware, allowed_hosts
from auditor.config import Settings


def _client() -> TestClient:
    return TestClient(app, base_url="http://localhost")


# --- HOST-01: hosts de loopback (com/sem porta, qualquer caixa) -------------------
@pytest.mark.parametrize("host", ["localhost", "localhost:8020", "127.0.0.1:8020",
                                  "[::1]", "[::1]:8020", "LOCALHOST:5173"])
def test_loopback_hosts_are_served(host):
    r = _client().get("/health", headers={"host": host})
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# --- HOST-02: qualquer outro Host → 400 e a rota não executa ----------------------
@pytest.mark.parametrize("host", ["evil.example", "evil.example:8020", "localhost.evil.example",
                                  "127.0.0.1.nip.io", "[::2]:8020"])
def test_foreign_hosts_are_rejected(host):
    r = _client().get("/fs/browse", headers={"host": host})
    assert r.status_code == 400
    assert r.text == "Host não permitido."


def test_rejected_request_does_not_run_the_route(monkeypatch, tmp_path):
    calls = []

    class _SpyStore:
        def create(self, *a, **k):
            calls.append(a)

    monkeypatch.setattr(routes, "get_store", lambda: _SpyStore())
    r = _client().post("/audits", json={"project_path": str(tmp_path)},
                       headers={"host": "evil.example"})
    assert r.status_code == 400
    assert calls == []


# --- HOST-03: Host ausente/vazio → 400 ---------------------------------------------
def test_empty_host_is_rejected():
    r = _client().get("/health", headers={"host": ""})
    assert r.status_code == 400


# --- HOST-04: extras via AUDITOR_ALLOWED_HOSTS --------------------------------------
def test_extra_hosts_from_setting_are_allowed(monkeypatch):
    monkeypatch.setenv("AUDITOR_ALLOWED_HOSTS", "a.local, B.local")
    hosts = allowed_hosts(Settings().allowed_hosts)

    mini = FastAPI()
    mini.add_middleware(LocalHostOnlyMiddleware, allowed=hosts)
    mini.get("/ping")(lambda: {"ok": True})
    c = TestClient(mini, base_url="http://localhost")

    assert c.get("/ping", headers={"host": "a.local:8020"}).status_code == 200
    assert c.get("/ping", headers={"host": "b.local"}).status_code == 200
    assert c.get("/ping", headers={"host": "localhost"}).status_code == 200  # defaults mantidos
    assert c.get("/ping", headers={"host": "c.local"}).status_code == 400


# --- HOST-04 (ligação no app real): a env chega ao middleware da app de produção -----
def test_real_app_reads_allowed_hosts_from_env(tmp_path):
    import os
    import subprocess
    import sys

    code = (
        "from fastapi.testclient import TestClient\n"
        "from auditor.api.main import app\n"
        "c = TestClient(app, base_url='http://localhost')\n"
        "print(c.get('/health', headers={'host': 'a.local'}).status_code,"
        " c.get('/health', headers={'host': 'z.local'}).status_code)\n"
    )
    env = {**os.environ, "AUDITOR_ALLOWED_HOSTS": "a.local", "HOME": str(tmp_path)}
    proc = subprocess.run([sys.executable, "-c", code], env=env, cwd=tmp_path,
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.split()[-2:] == ["200", "400"]


# --- HOST-02 (ordem): até o preflight CORS é barrado por Host estrangeiro -------------
def test_cors_preflight_with_foreign_host_is_rejected():
    r = _client().options("/audits", headers={
        "host": "evil.example", "origin": "http://localhost:5173",
        "access-control-request-method": "POST",
    })
    assert r.status_code == 400
    assert r.text == "Host não permitido."


# --- HOST-02 (parsing estrito): formatos ambíguos/duplicados são rejeitados -----------
@pytest.mark.parametrize("host", ["localhost:evil", "[::1]evil.example", "localhost:80:80",
                                  "local host", "[::1"])
def test_malformed_hosts_are_rejected(host):
    assert _client().get("/health", headers={"host": host}).status_code == 400


def test_duplicate_host_headers_are_rejected():
    mini = FastAPI()
    mini.add_middleware(LocalHostOnlyMiddleware)
    mini.get("/ping")(lambda: {"ok": True})

    import asyncio
    sent = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(msg):
        sent.append(msg)

    scope = {"type": "http", "method": "GET", "path": "/ping", "raw_path": b"/ping",
             "query_string": b"", "root_path": "", "scheme": "http", "http_version": "1.1",
             "server": ("127.0.0.1", 8020), "client": ("127.0.0.1", 5000),
             "headers": [(b"host", b"localhost"), (b"host", b"evil.example")]}
    asyncio.run(mini(scope, receive, send))
    assert sent[0]["status"] == 400


# --- HOST-03/04: extra inválido na env não pode abrir a porta para Host vazio ---------
def test_invalid_extra_does_not_allow_empty_or_malformed_host():
    hosts = allowed_hosts("bad host, a.local")
    assert "" not in hosts
    mini = FastAPI()
    mini.add_middleware(LocalHostOnlyMiddleware, allowed=hosts)
    mini.get("/ping")(lambda: {"ok": True})
    c = TestClient(mini, base_url="http://localhost")
    assert c.get("/ping", headers={"host": ""}).status_code == 400
    assert c.get("/ping", headers={"host": "localhost:evil"}).status_code == 400
    assert c.get("/ping", headers={"host": "a.local"}).status_code == 200
