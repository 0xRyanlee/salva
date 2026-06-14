"""SERP cache and URL content cache using diskcache.

Two independent caches:
  SERPCache     — search result pages (provider + query + region → list[dict])
  URLContentCache — fetched page content (url → bytes)

Both require `diskcache` (optional dependency). If not installed, all operations
are no-ops and the pipeline continues without caching.

Cache location: $SALVA_CACHE_DIR (default: ./data/cache/)
TTL: configurable per-cache; defaults:
  SERP: 24h (fresh search results)
  URL content: 72h (page content changes slowly)
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger("salva.retrieval.cache")

_CACHE_DIR = os.getenv("SALVA_CACHE_DIR", str(Path("data") / "cache"))
_SERP_TTL = int(os.getenv("SALVA_SERP_CACHE_TTL", str(24 * 3600)))       # 24 h
_URL_TTL  = int(os.getenv("SALVA_URL_CACHE_TTL",  str(72 * 3600)))       # 72 h

try:
    import diskcache as _dc
    _DC_AVAILABLE = True
except ImportError:
    _dc = None  # type: ignore[assignment]
    _DC_AVAILABLE = False


def _serp_key(provider: str, query: str, region: str = "", time_filter: str = "") -> str:
    raw = f"{provider}:{query.strip().lower()}:{region.lower()}:{time_filter}"
    return "serp:" + hashlib.sha256(raw.encode()).hexdigest()[:32]


def _url_key(url: str) -> str:
    return "url:" + hashlib.sha256(url.encode()).hexdigest()[:32]


class SERPCache:
    """Cache for search engine result pages."""

    def __init__(self, cache_dir: str = _CACHE_DIR, ttl: int = _SERP_TTL) -> None:
        self._ttl = ttl
        self._cache: Any = None
        if _DC_AVAILABLE:
            Path(cache_dir).mkdir(parents=True, exist_ok=True)
            self._cache = _dc.Cache(os.path.join(cache_dir, "serp"))

    def get(
        self,
        provider: str,
        query: str,
        region: str = "",
        time_filter: str = "",
    ) -> list[dict] | None:
        if self._cache is None:
            return None
        key = _serp_key(provider, query, region, time_filter)
        hit = self._cache.get(key)
        if hit is not None:
            logger.debug("serp cache HIT: %s %r", provider, query[:40])
        return hit  # type: ignore[return-value]

    def set(
        self,
        provider: str,
        query: str,
        results: list[dict],
        region: str = "",
        time_filter: str = "",
    ) -> None:
        if self._cache is None or not results:
            return
        key = _serp_key(provider, query, region, time_filter)
        self._cache.set(key, results, expire=self._ttl)

    def invalidate(self, provider: str, query: str, region: str = "", time_filter: str = "") -> None:
        if self._cache is None:
            return
        key = _serp_key(provider, query, region, time_filter)
        self._cache.delete(key)

    @property
    def available(self) -> bool:
        return self._cache is not None


class URLContentCache:
    """Cache for fetched URL content (bytes)."""

    def __init__(self, cache_dir: str = _CACHE_DIR, ttl: int = _URL_TTL) -> None:
        self._ttl = ttl
        self._cache: Any = None
        if _DC_AVAILABLE:
            Path(cache_dir).mkdir(parents=True, exist_ok=True)
            self._cache = _dc.Cache(os.path.join(cache_dir, "url_content"))

    def get(self, url: str) -> bytes | None:
        if self._cache is None:
            return None
        key = _url_key(url)
        hit = self._cache.get(key)
        if hit is not None:
            logger.debug("url cache HIT: %s", url[:80])
        return hit  # type: ignore[return-value]

    def set(self, url: str, content: bytes) -> None:
        if self._cache is None or not content:
            return
        self._cache.set(_url_key(url), content, expire=self._ttl)

    @property
    def available(self) -> bool:
        return self._cache is not None


# Module-level shared instances (one cache per process)
_serp_cache: SERPCache | None = None
_url_cache: URLContentCache | None = None


def get_serp_cache() -> SERPCache:
    global _serp_cache
    if _serp_cache is None:
        _serp_cache = SERPCache()
    return _serp_cache


def get_url_cache() -> URLContentCache:
    global _url_cache
    if _url_cache is None:
        _url_cache = URLContentCache()
    return _url_cache
