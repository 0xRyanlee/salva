"""
Marginalia Search retrieval source.

Marginalia runs its own web crawler index (independent of Google/Bing), biased
toward smaller/technical/B2B sites that major indexes de-prioritize.  The public
API requires no authentication and is free to use under AGPL-3.0.

API: https://api.marginalia.nu/public/search/{query}?page={n}
Response: { results: [ {url, title, description, quality, format}, ... ] }

Environment:
  MARGINALIA_BASE_URL  — override the public instance (self-hosted)
  MARGINALIA_ENABLED   — set "false" to disable (default: true)
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

logger = logging.getLogger("salva.retrieval.marginalia")

_DEFAULT_BASE = "https://api.marginalia.nu/public/search"


def _marginalia_enabled() -> bool:
    return os.getenv("MARGINALIA_ENABLED", "true").lower() not in ("0", "false", "no")


class MarginaliaRetriever:
    strategy = "anchor"

    def __init__(self, policy: RetrievalPolicy):
        self.policy = policy
        base = os.getenv("MARGINALIA_BASE_URL", "").rstrip("/") or _DEFAULT_BASE
        self._base = base
        self.last_attempts: list[RetrievalAttempt] = []

    def search(self, query: str, n: int = 10) -> list[dict[str, Any]]:
        self.last_attempts = []
        if not _marginalia_enabled():
            return []

        results: list[dict[str, Any]] = []
        page = 1
        while len(results) < n:
            batch = self._fetch_page(query, page)
            if not batch:
                break
            results.extend(batch)
            if len(batch) < 10:
                break
            page += 1

        trimmed = results[:n]
        self.last_attempts.append(
            RetrievalAttempt(
                provider="marginalia",
                base_url=self._base,
                mode=self.policy.mode,
                result_count=len(trimmed),
                succeeded=bool(trimmed),
                format_used="json",
            )
        )
        return trimmed

    def _fetch_page(self, query: str, page: int) -> list[dict[str, Any]]:
        encoded = urllib.parse.quote(query, safe="")
        params = f"?page={page}" if page > 1 else ""
        url = f"{self._base}/{encoded}{params}"
        try:
            raw = http_get(
                url,
                headers={"Accept": "application/json"},
                timeout=self.policy.request_timeout,
            )
            data = json.loads(raw)
            items: list[dict[str, Any]] = []
            for r in data.get("results", []):
                href = r.get("url", "")
                if not href:
                    continue
                items.append(
                    {
                        "title": r.get("title", ""),
                        "url": href,
                        "snippet": r.get("description", ""),
                        "engine": "marginalia",
                        "retrieval_instance": self._base,
                        "quality": r.get("quality", 0.0),
                    }
                )
            return items
        except Exception as exc:
            logger.debug("Marginalia page %d failed: %s", page, exc)
            self.last_attempts.append(
                RetrievalAttempt(
                    provider="marginalia",
                    base_url=self._base,
                    mode=self.policy.mode,
                    result_count=0,
                    succeeded=False,
                    error=str(exc),
                    format_used="json",
                )
            )
            return []
