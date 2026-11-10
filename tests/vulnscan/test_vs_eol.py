"""endoflife.date + avaliação de runtime (spec: .specs/features/vuln-scan — RT-02..04, OSV-03)."""
from __future__ import annotations

import httpx
import pytest

from auditor.vulnscan.models import RuntimeDecl
from auditor.vulnscan.runtime import evaluate
from auditor.vulnscan.sources.eol import EOL_BASE_URL, EndOfLifeClient

PAYLOAD = {
    "nodejs": [("22", False, "22.20.0"), ("20", False, "20.19.5"), ("16", True, "16.20.2")],
    "php": [("8.3", False, "8.3.26"), ("8.1", True, "8.1.33")],
    "python": [("3.12", False, "3.12.12"), ("3.8", True, "3.8.20")],
}


def _handler(request: httpx.Request) -> httpx.Response:
    product = request.url.path.rsplit("/", 1)[1]
    if product not in PAYLOAD:
        return httpx.Response(404)
    releases = [{"name": n, "isEol": eol, "latest": {"name": latest}} for n, eol, latest in PAYLOAD[product]]
    return httpx.Response(200, json={"schema_version": "1.2.0", "result": {"name": product, "releases": releases}})


@pytest.fixture
def eol():
    calls = []

    def handler(request):
        calls.append(request.url.path)
        return _handler(request)

    client = EndOfLifeClient(http=httpx.Client(base_url=EOL_BASE_URL, transport=httpx.MockTransport(handler)))
    client.calls = calls
    return client


def test_cycles_parsed_and_memoized(eol):
    cycles = eol.cycles("nodejs")
    assert [(c.name, c.is_eol, c.latest) for c in cycles][:2] == [("22", False, "22.20.0"), ("20", False, "20.19.5")]
    eol.cycles("nodejs")
    assert eol.calls == ["/api/v1/products/nodejs"]


def test_unknown_product_or_error_is_recorded(eol):
    assert eol.cycles("cobol") is None and eol.errors


@pytest.mark.parametrize("url", ["http://endoflife.date", "https://evil.example"])
def test_only_https_endoflife_host(url):
    with pytest.raises(ValueError):
        EndOfLifeClient(http=httpx.Client(base_url=url))


def _decl(product, value):
    return RuntimeDecl(product, value, "f", 1, value)


@pytest.mark.parametrize("product, value, status, severity", [
    ("nodejs", "16", "finding", "high"),          # ciclo EOL (só ciclo)
    ("nodejs", "20", "ok", None),                 # ciclo suportado, sem patch para comparar
    ("nodejs", "16.20.2", "finding", "high"),     # exato em ciclo EOL
    ("nodejs", "20.11.1", "finding", "medium"),   # exato abaixo do último patch
    ("nodejs", "20.19.5", "ok", None),            # exato no último patch
    ("nodejs", ">=16", "finding", "medium"),      # faixa permite ciclo EOL
    ("nodejs", ">=20", "ok", None),
    ("php", "8.1", "finding", "high"),
    ("php", "^8.1", "finding", "medium"),
    ("php", "8.3.20", "finding", "medium"),
    ("python", "3.12.12", "ok", None),
    ("python", ">=3.8", "finding", "medium"),
    ("python", "3.99", "unknown", None),          # ciclo inexistente (RT-04)
    ("nodejs", "lts", "unknown", None),           # tag sem versão (RT-04)
])
def test_evaluate(eol, product, value, status, severity):
    result = evaluate(_decl(product, value), eol.cycles(product))
    assert result.status == status
    assert (result.severity if status == "finding" else None) == severity
    if status == "finding":
        assert result.message                       # explicação para o achado


def test_evaluate_without_cycles_is_unknown():
    assert evaluate(_decl("nodejs", "16"), None).status == "unknown"
