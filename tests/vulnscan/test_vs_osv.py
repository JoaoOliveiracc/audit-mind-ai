"""OSVClient (spec: .specs/features/vuln-scan — OSV-01..03). Sem rede: httpx.MockTransport."""
from __future__ import annotations

import json

import httpx
import pytest

from auditor.vulnscan.models import Dependency
from auditor.vulnscan.sources.osv import OSV_BASE_URL, OSVClient

LODASH = {
    "id": "GHSA-35jh-r3h4-6jhm", "aliases": ["CVE-2021-23337"], "summary": "Command Injection in lodash",
    "database_specific": {"severity": "HIGH"},
    "affected": [
        {"package": {"ecosystem": "npm", "name": "lodash"},
         "ranges": [{"type": "SEMVER", "events": [{"introduced": "0"}, {"fixed": "3.10.2"},
                                                  {"introduced": "4.0.0"}, {"fixed": "4.17.21"}]}]},
        {"package": {"ecosystem": "npm", "name": "lodash-es"},
         "ranges": [{"type": "SEMVER", "events": [{"introduced": "0"}, {"fixed": "9.9.9"}]}]},
    ],
}
NOFIX = {"id": "GHSA-nofix", "aliases": [], "summary": "Sem correção",
         "severity": [{"type": "CVSS_V3", "score": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"}],
         "affected": [{"package": {"ecosystem": "npm", "name": "lodash"},
                       "ranges": [{"type": "SEMVER", "events": [{"introduced": "0"}]}]}]}


def _dep(name="lodash", version="4.17.15", eco="npm"):
    return Dependency(ecosystem=eco, name=name, version=version, file="package-lock.json", line=1)


class _Server:
    """Simula o api.osv.dev e registra o que recebeu."""

    def __init__(self, vulns_for=None, records=None, fail_paths=(), big=False):
        self.vulns_for = vulns_for or (lambda q: [])
        self.records = records or {}
        self.fail_paths, self.big = set(fail_paths), big
        self.batches: list[list[dict]] = []
        self.fetched: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.path in self.fail_paths:
            return httpx.Response(500, text="erro")
        if request.url.path == "/v1/querybatch":
            queries = json.loads(request.content)["queries"]
            self.batches.append(queries)
            return httpx.Response(200, json={"results": [self.vulns_for(q) for q in queries]})
        vuln_id = request.url.path.rsplit("/", 1)[1]
        self.fetched.append(vuln_id)
        if self.big:
            return httpx.Response(200, content=b"{" + b" " * (6 * 1024 * 1024) + b"}")
        return httpx.Response(200, json=self.records[vuln_id])


def _client(server, **kw):
    http = httpx.Client(base_url=OSV_BASE_URL, transport=httpx.MockTransport(server))
    return OSVClient(http=http, **kw)


# --- OSV-01: lotes, paginação, memo --------------------------------------------------
def test_querybatch_chunks_of_500():
    server = _Server()
    client = _client(server)
    deps = [_dep(name=f"p{i}") for i in range(1_200)]
    client.query(deps)
    assert [len(b) for b in server.batches] == [500, 500, 200]


def test_pagination_requests_only_paginated_queries():
    def vulns_for(q):
        if q["package"]["name"] == "b" and "page_token" not in q:
            return {"vulns": [{"id": "V1"}], "next_page_token": "T"}
        if q.get("page_token") == "T":
            return {"vulns": [{"id": "V2"}]}
        return {"vulns": []}

    server = _Server(vulns_for)
    hits = _client(server).query([_dep("a"), _dep("b")])
    assert server.batches[1] == [{"package": {"ecosystem": "npm", "name": "b"}, "version": "4.17.15",
                                  "page_token": "T"}]
    assert hits[("npm", "b", "4.17.15")] == ["V1", "V2"]


def test_each_advisory_fetched_once_and_fixed_version_chosen_by_range():
    server = _Server(lambda q: {"vulns": [{"id": "GHSA-35jh-r3h4-6jhm"}]},
                     {"GHSA-35jh-r3h4-6jhm": LODASH})
    client = _client(server)
    d4, d3 = _dep(version="4.17.15"), _dep(version="3.9.0")
    hits = client.query([d4, d3])
    advisories = client.advisories({i for ids in hits.values() for i in ids})
    assert server.fetched == ["GHSA-35jh-r3h4-6jhm"]                      # memo
    adv = advisories["GHSA-35jh-r3h4-6jhm"]
    assert (adv.cves, adv.summary, adv.severity) == (("CVE-2021-23337",), "Command Injection in lodash", "high")
    assert adv.fixed_for(d4) == "4.17.21" and adv.fixed_for(d3) == "3.10.2"   # OSV-02: faixa certa
    assert adv.fixed_for(_dep(name="lodash-es")) == "9.9.9"


def test_no_fix_published_and_severity_fallback():
    server = _Server(lambda q: {"vulns": [{"id": "GHSA-nofix"}]}, {"GHSA-nofix": NOFIX})
    client = _client(server)
    adv = client.advisories({"GHSA-nofix"})["GHSA-nofix"]
    assert adv.fixed_for(_dep()) is None and adv.severity == "critical"


def test_pypi_names_are_normalized_when_matching_affected():
    record = {"id": "PYSEC-1", "aliases": ["CVE-1"], "summary": "s", "database_specific": {"severity": "LOW"},
              "affected": [{"package": {"ecosystem": "PyPI", "name": "Django"},
                            "ranges": [{"type": "ECOSYSTEM", "events": [{"introduced": "0"}, {"fixed": "3.2.1"}]}]}]}
    client = _client(_Server(records={"PYSEC-1": record}))
    adv = client.advisories({"PYSEC-1"})["PYSEC-1"]
    assert adv.fixed_for(_dep(name="django", version="3.2.0", eco="PyPI")) == "3.2.1"


# --- OSV-03: privacidade, host, limites, falhas ----------------------------------------
def test_payload_has_only_ecosystem_name_version():
    server = _Server()
    _client(server).query([_dep()])
    assert server.batches == [[{"package": {"ecosystem": "npm", "name": "lodash"}, "version": "4.17.15"}]]


@pytest.mark.parametrize("url", ["http://api.osv.dev", "https://evil.example", "https://api.osv.dev.evil.example"])
def test_only_https_osv_host_is_allowed(url):
    with pytest.raises(ValueError):
        OSVClient(http=httpx.Client(base_url=url))


def test_default_client_has_15s_timeout():
    client = OSVClient()
    assert client.http.timeout.read == 15.0
    client.close()


def test_oversized_response_is_an_error_not_a_crash():
    server = _Server(records={}, big=True)
    client = _client(server)
    assert client.advisories({"X"}) == {}
    assert any("5 MB" in e for e in client.errors)


def test_http_errors_are_recorded_never_raised():
    server = _Server(fail_paths={"/v1/querybatch"})
    client = _client(server)
    assert client.query([_dep()]) == {}
    assert client.errors and "querybatch" in client.errors[0]


def test_advisory_id_is_url_encoded_in_path():
    seen = []

    def handler(request):
        seen.append(request.url.raw_path)
        return httpx.Response(404)

    client = OSVClient(http=httpx.Client(base_url=OSV_BASE_URL, transport=httpx.MockTransport(handler)))
    client.advisories({"../../v1/querybatch"})
    assert seen == [b"/v1/vulns/..%2F..%2Fv1%2Fquerybatch"]
