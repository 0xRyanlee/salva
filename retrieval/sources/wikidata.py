"""
Wikidata retrieval source.

Wikidata's wbsearchentities API resolves a query string (in any script) to
structured entities with a stable QID and cross-language labels/aliases.
Free, no API key required. Verified live: querying with the Chinese alias
"台積電" and language=en still resolves to entity Q713418 with English
label "TSMC" -- wbsearchentities matches against all languages' aliases
regardless of the `language` param, which only controls which language the
returned label/description are displayed in. This makes it a stronger
cross-language entity-alignment signal than embedding similarity alone
(see DEVELOPMENT_PROGRESS.md's cosine("台積電", "TSMC") ~= 0.04 finding).

API: https://www.wikidata.org/w/api.php?action=wbsearchentities&search={query}&language=en&format=json&limit={n}
Response: { search: [ {id, url, label, description, ...}, ... ] }

Environment:
  WIKIDATA_ENABLED  — set "false" to disable (default: true)
"""
from __future__ import annotations

import json
import logging
import os
import urllib.parse
from typing import Any

from retrieval.http import http_get
from retrieval.models import RetrievalAttempt
from salva_core.schemas import RetrievalPolicy

logger = logging.getLogger("salva.retrieval.wikidata")

_BASE_URL = "https://www.wikidata.org/w/api.php"


def _wikidata_enabled() -> bool:
    return os.getenv("WIKIDATA_ENABLED", "true").lower() not in ("0", "false", "no")


class WikidataRetriever:
    strategy = "anchor"

    def __init__(self, policy: RetrievalPolicy):
        self.policy = policy
        self.last_attempts: list[RetrievalAttempt] = []

    def search(self, query: str, n: int = 10) -> list[dict[str, Any]]:
        self.last_attempts = []
        if not _wikidata_enabled():
            return []

        # wbsearchentities caps at 50 results per request; n is normally <= 20.
        limit = max(1, min(n, 50))
        params = urllib.parse.urlencode({
            "action": "wbsearchentities",
            "search": query,
            "language": "en",
            "format": "json",
            "limit": limit,
        })
        url = f"{_BASE_URL}?{params}"
        try:
            raw = http_get(
                url,
                headers={"Accept": "application/json"},
                timeout=self.policy.request_timeout,
            )
            data = json.loads(raw)
            items: list[dict[str, Any]] = []
            for hit in data.get("search", []):
                entity_url = hit.get("url", "")
                if entity_url.startswith("//"):
                    entity_url = f"https:{entity_url}"
                if not entity_url:
                    continue
                items.append({
                    "title": hit.get("label", hit.get("id", "")),
                    "url": entity_url,
                    "snippet": hit.get("description", ""),
                    "engine": "wikidata",
                    "retrieval_instance": _BASE_URL,
                    "wikidata_qid": hit.get("id", ""),
                })
            self.last_attempts.append(
                RetrievalAttempt(
                    provider="wikidata",
                    base_url=_BASE_URL,
                    mode=self.policy.mode,
                    result_count=len(items),
                    succeeded=bool(items),
                    format_used="json",
                )
            )
            return items[:n]
        except Exception as exc:
            logger.debug("Wikidata search failed: %s", exc)
            self.last_attempts.append(
                RetrievalAttempt(
                    provider="wikidata",
                    base_url=_BASE_URL,
                    mode=self.policy.mode,
                    result_count=0,
                    succeeded=False,
                    error=str(exc),
                    format_used="json",
                )
            )
            return []
