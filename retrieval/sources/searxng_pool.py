"""Public SearXNG instance pool with per-instance health gating.

Instances are loaded from a JSON config file (SEARXNG_POOL_CONFIG env var)
or the built-in default list. Each instance gets an independent ProviderHealth
entry. On failure (403/429/timeout), the instance goes into cooldown for 4 hours.
At most 1–2 instances are tried per query to avoid abusing public services.

Config format (searxng_instances.json):
  [{"url": "https://searx.be", "region": "eu", "enabled": true}]
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

from retrieval.health import ProviderErrorType, ProviderHealthRegistry, get_health_registry
from retrieval.http import http_get
from salva_core.schemas import RetrievalPolicy

logger = logging.getLogger("salva.retrieval.searxng_pool")

_DEFAULT_INSTANCES = [
    {"url": "https://searx.be",            "region": "eu",    "enabled": True},
    {"url": "https://search.inetol.net",   "region": "eu",    "enabled": True},
    {"url": "https://paulgo.io",           "region": "eu",    "enabled": True},
    {"url": "https://searxng.site",        "region": "global","enabled": True},
    {"url": "https://search.disroot.org",  "region": "eu",    "enabled": True},
]

_MAX_TRIES_PER_QUERY = 2  # don't hammer public instances


def _load_instances() -> list[dict]:
    path = os.getenv("SEARXNG_POOL_CONFIG", "")
    if path:
        try:
            with open(path) as f:
                return json.load(f)
        except Exception as exc:
            logger.warning("searxng_pool: could not load config %s: %s", path, exc)
    return _DEFAULT_INSTANCES


class PublicSearXNGPool:
    """
    Try public SearXNG instances in round-robin order, skipping instances in cooldown.
    Falls back gracefully when all instances are in cooldown.
    """

    strategy = "anchor"

    def __init__(self, policy: RetrievalPolicy, health: ProviderHealthRegistry | None = None) -> None:
        self.policy = policy
        self._health = health or get_health_registry()
        self._instances = [i for i in _load_instances() if i.get("enabled", True)]

    def search(self, query: str, n: int = 10) -> list[dict[str, Any]]:
        tries = 0
        for instance in self._instances:
            if tries >= _MAX_TRIES_PER_QUERY:
                break
            pid = f"searxng_pool:{instance['url']}"
            if not self._health.is_usable(pid):
                continue

            results = self._query_instance(instance["url"], query, n)
            if results is not None:
                self._health.record_success(pid)
                return results
            tries += 1
        return []

    def _query_instance(self, base: str, query: str, n: int) -> list[dict[str, Any]] | None:
        import urllib.parse as _ul
        params = _ul.urlencode({
            "q": query,
            "format": "json",
            "language": self.policy.region_hint or "en-US",
        })
        url = f"{base.rstrip('/')}/search?{params}"
        pid = f"searxng_pool:{base}"
        try:
            raw = http_get(url, timeout=self.policy.request_timeout)
            data = json.loads(raw)
            results = data.get("results", [])
            mapped = [
                {
                    "title":    r.get("title", ""),
                    "url":      r.get("url", ""),
                    "snippet":  r.get("content", ""),
                    "engine":   "searxng_pool",
                    "retrieval_instance": base,
                }
                for r in results[:n]
                if r.get("url")
            ]
            return mapped
        except Exception as exc:
            err_str = str(exc).lower()
            if "403" in err_str:
                self._health.record_failure(pid, ProviderErrorType.BLOCKED)
            elif "429" in err_str:
                self._health.record_failure(pid, ProviderErrorType.RATE_LIMIT)
            elif "timeout" in err_str:
                self._health.record_failure(pid, ProviderErrorType.TIMEOUT)
            else:
                self._health.record_failure(pid, ProviderErrorType.NETWORK_ERROR)
            logger.debug("searxng_pool: %s failed: %s", base, exc)
            return None
