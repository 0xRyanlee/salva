from __future__ import annotations

import json
import logging
import os
import random
import time
import urllib.parse
import urllib.request
from typing import Any

from retrieval.models import RetrievalAttempt
from salva_core.schemas import RetrievalPolicy

logger = logging.getLogger("salva.retrieval.whoogle")

WHOOGLE_URL = os.getenv("WHOOGLE_URL", "").rstrip("/")

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/123.0 Safari/537.36",
]


class WhoogleRetriever:
    strategy = "dive"

    def __init__(self, policy: RetrievalPolicy, base_url: str | None = None):
        self.policy = policy
        self.base_url = (base_url or WHOOGLE_URL).rstrip("/")
        self.last_attempts: list[RetrievalAttempt] = []

    def search(self, query: str, n: int = 10) -> list[dict[str, Any]]:
        self.last_attempts = []
        if not self.base_url:
            return []

        params = urllib.parse.urlencode({"q": query, "format": "json"})
        url = f"{self.base_url}/search?{params}"
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": random.choice(USER_AGENTS),
                    "Accept": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=self.policy.request_timeout) as resp:
                data = json.load(resp)
            time.sleep(self.policy.request_delay)
            raw_results = data.get("results", [])[:n]
            results = [
                {
                    "title": item.get("text", ""),
                    "url": item.get("href", ""),
                    "snippet": item.get("text", ""),
                    "engine": "whoogle",
                    "retrieval_instance": self.base_url,
                }
                for item in raw_results
                if item.get("href")
            ]
            self.last_attempts.append(
                RetrievalAttempt(
                    provider="whoogle",
                    base_url=self.base_url,
                    mode=self.policy.mode,
                    result_count=len(results),
                    succeeded=bool(results),
                    format_used="json",
                )
            )
            return results
        except Exception as exc:
            logger.debug("Whoogle failed: %s", exc)
            self.last_attempts.append(
                RetrievalAttempt(
                    provider="whoogle",
                    base_url=self.base_url,
                    mode=self.policy.mode,
                    result_count=0,
                    succeeded=False,
                    error=str(exc),
                    format_used="json",
                )
            )
            return []
