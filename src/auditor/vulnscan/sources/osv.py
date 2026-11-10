"""Gateway do OSV.dev: ``POST /v1/querybatch`` + ``GET /v1/vulns/{id}`` (OSV-01..03)."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from threading import Lock
from typing import Any, Iterable, Sequence
from urllib.parse import quote

import httpx

from ..models import Dependency
from ..severity import severity_from_osv
from ..versions import in_range, normalize_name
from . import SourceError, checked_client, get_json

OSV_BASE_URL = "https://api.osv.dev"
_CHUNK = 500
_MAX_PAGES = 10
# Formatos inesperados da resposta (lista no lugar de objeto etc.): erro registrado, nunca exceção.
_MALFORMED = (SourceError, KeyError, TypeError, AttributeError, ValueError)
DepKey = tuple[str, str, str]


def dep_key(dep: Dependency) -> DepKey:
    return (dep.ecosystem, normalize_name(dep.ecosystem, dep.name), dep.version)


@dataclass(frozen=True)
class Advisory:
    id: str
    cves: tuple[str, ...]
    summary: str
    severity: str
    severity_note: str | None
    affected: tuple[tuple[str, str, tuple[tuple[str, str], ...]], ...]   # (eco, nome normalizado, eventos)

    def fixed_for(self, dep: Dependency) -> str | None:
        """Versão corrigida da faixa que contém a versão instalada (``None``: sem correção)."""
        name = normalize_name(dep.ecosystem, dep.name)
        for eco, affected_name, events in self.affected:
            if eco != dep.ecosystem or affected_name != name:
                continue
            introduced: str | None = None
            for kind, value in events:
                if kind == "introduced":
                    introduced = value
                elif kind == "fixed" and introduced is not None:
                    if in_range(dep.ecosystem, dep.version, introduced, value):
                        return value
                    introduced = None
        return None


def _parse_advisory(record: dict[str, Any]) -> Advisory:
    severity, note = severity_from_osv(record)
    affected = []
    for entry in record.get("affected") or []:
        pkg = entry.get("package") or {}
        eco, name = str(pkg.get("ecosystem", "")), str(pkg.get("name", ""))
        events: list[tuple[str, str]] = []
        for rng in entry.get("ranges") or []:
            if rng.get("type") in ("SEMVER", "ECOSYSTEM"):
                for event in rng.get("events") or []:
                    events.extend((k, str(v)) for k, v in event.items() if k in ("introduced", "fixed"))
        affected.append((eco, normalize_name(eco, name), tuple(events)))
    ids = [record.get("id", ""), *(record.get("aliases") or [])]
    return Advisory(id=str(record["id"]), cves=tuple(dict.fromkeys(i for i in ids if str(i).startswith("CVE-"))),
                    summary=str(record.get("summary") or record.get("details") or "")[:300],
                    severity=severity, severity_note=note, affected=tuple(affected))


class OSVClient:
    """Nunca lança: falhas vão para ``errors`` (a varredura fica marcada como incompleta)."""

    def __init__(self, http: httpx.Client | None = None, workers: int = 8) -> None:
        self.http = checked_client(http, OSV_BASE_URL)
        self.workers = workers
        self.errors: list[str] = []
        self._memo: dict[str, Advisory] = {}
        self._lock = Lock()

    def close(self) -> None:
        self.http.close()

    def query(self, deps: Sequence[Dependency]) -> dict[DepKey, list[str]]:
        """IDs de advisories por dependência (só ``ecosystem``/``name``/``version`` saem)."""
        hits: dict[DepKey, list[str]] = {}
        keys = list(dict.fromkeys(dep_key(d) for d in deps))
        for start in range(0, len(keys), _CHUNK):
            pending: list[tuple[DepKey, str | None]] = [(k, None) for k in keys[start:start + _CHUNK]]
            for page in range(_MAX_PAGES):
                queries = [{"package": {"ecosystem": e, "name": n}, "version": v,
                            **({"page_token": tok} if tok else {})} for (e, n, v), tok in pending]
                try:
                    results = get_json(self.http, "POST", "/v1/querybatch", {"queries": queries})["results"]
                    if not isinstance(results, list) or len(results) != len(pending):
                        raise ValueError("resposta fora do formato esperado")
                    next_pending: list[tuple[DepKey, str | None]] = []
                    for (key, _tok), result in zip(pending, results):
                        result = result or {}
                        ids = [str(v["id"]) for v in result.get("vulns") or [] if "id" in v]
                        if ids:
                            hits.setdefault(key, []).extend(ids)
                        if result.get("next_page_token"):
                            next_pending.append((key, str(result["next_page_token"])))
                except _MALFORMED as exc:
                    self.errors.append(f"querybatch: {exc}")
                    break
                if not next_pending:
                    break
                if page == _MAX_PAGES - 1:      # nunca "completo" em silêncio
                    self.errors.append(f"querybatch: paginação excedeu {_MAX_PAGES} páginas para "
                                       f"{len(next_pending)} pacote(s); advisories restantes não consultados")
                pending = next_pending
        return hits

    def advisories(self, ids: Iterable[str]) -> dict[str, Advisory]:
        """Registros completos (cada id buscado uma única vez, em paralelo)."""
        wanted = [i for i in dict.fromkeys(ids) if i not in self._memo]
        with ThreadPoolExecutor(max_workers=max(1, min(self.workers, len(wanted) or 1))) as pool:
            for vuln_id, advisory in zip(wanted, pool.map(self._fetch, wanted)):
                if advisory is not None:
                    self._memo[vuln_id] = advisory
        return {i: self._memo[i] for i in ids if i in self._memo}

    def _fetch(self, vuln_id: str) -> Advisory | None:
        try:
            return _parse_advisory(get_json(self.http, "GET", f"/v1/vulns/{quote(vuln_id, safe='')}"))
        except _MALFORMED as exc:
            with self._lock:
                self.errors.append(f"vulns/{vuln_id}: {exc}")
            return None
