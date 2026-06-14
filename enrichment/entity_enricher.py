"""Wikidata entity metadata enricher.

Resolves a company name to its Wikidata Q-id plus English label and description.
Uses the MediaWiki wbsearchentities API — free, no authentication required.

The enricher is intentionally minimal: it returns what wikidata.org returns
in a single search call. P452 (industry) and P17 (country) require additional
API round-trips and are deferred to a future enrichment pass.

Environment:
  WIKIDATA_ENABLED — set "false" to disable (default: true)
  WIKIDATA_BASE_URL — override base URL (default: https://www.wikidata.org)

Usage:
  from enrichment.entity_enricher import WikidataEnricher, WikidataEntityMeta
  meta = WikidataEnricher().enrich("TSMC")
  if meta:
      print(meta.qid, meta.description)
"""
from __future__ import annotations

import json
import logging
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass

logger = logging.getLogger("salva.enrichment.wikidata")

_DEFAULT_BASE = "https://www.wikidata.org"
_TIMEOUT = 10.0
_USER_AGENT = "Salva-Runtime/1.0 (entity enrichment; contact: ryan910814@gmail.com)"


def _enabled() -> bool:
    return os.getenv("WIKIDATA_ENABLED", "true").lower() not in ("0", "false", "no")


@dataclass(frozen=True)
class WikidataEntityMeta:
    qid: str           # e.g. "Q95"
    label: str         # e.g. "Google"
    description: str   # e.g. "American technology company"


class WikidataEnricher:
    """Search Wikidata for a company name and return its Q-id + description."""

    def __init__(self, base_url: str | None = None, timeout: float = _TIMEOUT) -> None:
        self._base = (base_url or os.getenv("WIKIDATA_BASE_URL", "").rstrip("/")
                      or _DEFAULT_BASE)
        self._timeout = timeout

    def enrich(self, name: str) -> WikidataEntityMeta | None:
        """Return the top Wikidata match for `name`, or None on any failure."""
        if not _enabled() or not name.strip():
            return None
        params = urllib.parse.urlencode({
            "action": "wbsearchentities",
            "search": name.strip(),
            "language": "en",
            "type": "item",
            "limit": 1,
            "format": "json",
        })
        url = f"{self._base}/w/api.php?{params}"
        try:
            req = urllib.request.Request(
                url,
                headers={"Accept": "application/json", "User-Agent": _USER_AGENT},
            )
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                data = json.load(resp)
            results = data.get("search", [])
            if not results:
                return None
            hit = results[0]
            qid = hit.get("id", "").strip()
            label = hit.get("label", "").strip()
            description = hit.get("description", "").strip()
            if not qid or not label:
                return None
            return WikidataEntityMeta(qid=qid, label=label, description=description)
        except Exception as exc:
            logger.debug("Wikidata enrich failed for %r: %s", name, exc)
            return None
