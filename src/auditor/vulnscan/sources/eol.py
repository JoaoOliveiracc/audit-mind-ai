"""Gateway do endoflife.date: ``GET /api/v1/products/{produto}`` (RT-02..04, OSV-03)."""
from __future__ import annotations

from urllib.parse import quote

import httpx

from ..models import Cycle
from . import SourceError, checked_client, get_json

EOL_BASE_URL = "https://endoflife.date"


class EndOfLifeClient:
    """Ciclos de release por produto (memo por execução). Nunca lança: falhas em ``errors``."""

    def __init__(self, http: httpx.Client | None = None) -> None:
        self.http = checked_client(http, EOL_BASE_URL)
        self.errors: list[str] = []
        self._memo: dict[str, list[Cycle] | None] = {}

    def close(self) -> None:
        self.http.close()

    def cycles(self, product: str) -> list[Cycle] | None:
        if product in self._memo:
            return self._memo[product]
        result: list[Cycle] | None
        try:
            data = get_json(self.http, "GET", f"/api/v1/products/{quote(product, safe='')}")
            result = [Cycle(name=str(r["name"]), is_eol=bool(r.get("isEol")),
                            latest=(r.get("latest") or {}).get("name"))
                      for r in data["result"]["releases"]]
        except (SourceError, KeyError, TypeError, AttributeError, ValueError) as exc:
            self.errors.append(f"endoflife/{product}: {exc}")
            result = None
        self._memo[product] = result
        return result
