"""
GLEIF (Global Legal Entity Identifier Foundation) resolver.

Translates a company name into its LEI code and canonical legal name using the
GLEIF fuzzy completions API. Free, no authentication required, covers 140+
jurisdictions and 2.5M+ registered entities.

API: https://api.gleif.org/api/v1/fuzzycompletions?q={name}&field=entity.legalName
Response: JSON:API envelope; each item has attributes.value (legal name) and
          relationships.lei-records.data.id (20-char LEI code).

Environment:
  GLEIF_ENABLED   — set "false" to disable all lookups (default: true)
  GLEIF_BASE_URL  — override base URL (self-hosted GLEIF mirror)

Usage:
  from salva_core.resolvers.gleif import gleif_lookup, GleifMatch
  match = gleif_lookup("GIGABYTE Technology")
  if match:
      print(match.lei, match.legal_name)
"""
from __future__ import annotations

import json
import logging
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass
from difflib import SequenceMatcher

_MIN_SIMILARITY = 0.6  # reject GLEIF results with token similarity below this

logger = logging.getLogger("salva.resolvers.gleif")

_DEFAULT_BASE = "https://api.gleif.org/api/v1"
_TIMEOUT = 10.0


def _gleif_enabled() -> bool:
    return os.getenv("GLEIF_ENABLED", "true").lower() not in ("0", "false", "no")


@dataclass(frozen=True)
class GleifMatch:
    lei: str
    legal_name: str


def gleif_lookup(name: str, top_k: int = 3) -> list[GleifMatch]:
    """
    Return up to `top_k` GLEIF matches for `name`, ordered by API relevance.

    Returns an empty list when GLEIF is disabled, the network is unavailable,
    or no matches are found. Never raises.
    """
    if not _gleif_enabled() or not name.strip():
        return []

    base = os.getenv("GLEIF_BASE_URL", "").rstrip("/") or _DEFAULT_BASE
    params = urllib.parse.urlencode({"q": name.strip(), "field": "entity.legalName"})
    url = f"{base}/fuzzycompletions?{params}"

    try:
        req = urllib.request.Request(
            url,
            headers={"Accept": "application/vnd.api+json"},
        )
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            data = json.load(resp)

        matches: list[GleifMatch] = []
        for item in data.get("data", [])[:top_k]:
            attrs = item.get("attributes", {})
            legal_name = attrs.get("value", "").strip()
            rel = item.get("relationships", {}).get("lei-records", {})
            lei = rel.get("data", {}).get("id", "").strip()
            if legal_name and lei:
                matches.append(GleifMatch(lei=lei, legal_name=legal_name))
        return matches

    except Exception as exc:
        logger.debug("GLEIF lookup for %r failed: %s", name, exc)
        return []


def _is_acceptable_match(query: str, candidate: str) -> bool:
    """Accept if query is a substring of candidate (abbreviation → full name) or similarity ≥ threshold."""
    q, c = query.lower().strip(), candidate.lower().strip()
    if q in c:
        return True
    return SequenceMatcher(None, q, c).ratio() >= _MIN_SIMILARITY


def gleif_resolve(name: str) -> str | None:
    """
    Return the canonical legal name for `name` from GLEIF, or None if no match.
    Uses the top-1 result only — suitable for single-entity resolution.
    Rejects results where the query is not a substring of the candidate and
    SequenceMatcher similarity is below _MIN_SIMILARITY.
    """
    matches = gleif_lookup(name, top_k=1)
    if not matches:
        return None
    candidate = matches[0].legal_name
    if not _is_acceptable_match(name, candidate):
        logger.debug("GLEIF candidate %r rejected for query %r", candidate, name)
        return None
    return candidate
