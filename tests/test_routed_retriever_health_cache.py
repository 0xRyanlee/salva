"""Tests for RoutedRetriever health gating + SERP cache integration."""
from __future__ import annotations

import tempfile
from unittest.mock import MagicMock

import pytest

from retrieval.cache import SERPCache
from retrieval.health import ProviderErrorType, ProviderHealthRegistry
from retrieval.router import RoutedRetriever, _classify_error, _provider_id
from salva_core.schemas import RetrievalPolicy

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _health() -> ProviderHealthRegistry:
    return ProviderHealthRegistry()


def _cache(tmp_path) -> SERPCache:
    return SERPCache(cache_dir=str(tmp_path / "serp"), ttl=3600)


def _retriever(tmp_path, health=None, cache=None) -> RoutedRetriever:
    r = RoutedRetriever(
        policy=RetrievalPolicy(),
        strategy="dive",
        health=health or _health(),
        cache=cache or _cache(tmp_path),
    )
    r.providers = []  # start empty; tests inject their own
    return r


# ---------------------------------------------------------------------------
# Mock providers
# ---------------------------------------------------------------------------

class _Provider:
    strategy = "dive"
    last_attempts: list = []

    def __init__(self, name: str, results: list[dict] | None = None, raises: Exception | None = None):
        self._name = name
        self._results = results or []
        self._raises = raises
        self.call_count = 0

    def search(self, query: str, n: int) -> list[dict]:
        self.call_count += 1
        if self._raises:
            raise self._raises
        return self._results


# ---------------------------------------------------------------------------
# Health gating — _search_sequential
# ---------------------------------------------------------------------------

def test_sequential_skips_provider_in_cooldown(tmp_path) -> None:
    health = _health()
    r = _retriever(tmp_path, health=health)

    good_results = [{"title": "ACME", "url": "https://acme.com", "snippet": "distributor of widgets"}]

    # Use distinct subclasses so class-name-based provider IDs differ
    class BadProvider(_Provider):
        pass

    class GoodProvider(_Provider):
        pass

    p_bad = BadProvider("bad")
    p_good = GoodProvider("good", results=good_results)
    r.providers = [p_bad, p_good]

    pid = "BadProvider"
    for _ in range(3):
        health.record_failure(pid, ProviderErrorType.BLOCKED)
    assert not health.is_usable(pid)

    results = r._search_sequential("test query", 5)
    assert p_bad.call_count == 0, "BadProvider should be skipped (in cooldown)"
    assert p_good.call_count == 1
    assert results == good_results


def test_sequential_records_success_on_content_hit(tmp_path) -> None:
    health = _health()
    r = _retriever(tmp_path, health=health)
    good = [{"title": "Corp A", "url": "https://a.com", "snippet": "full content here"}]
    p = _Provider("GoodProv", results=good)
    r.providers = [p]

    r._search_sequential("query", 5)
    pid = type(p).__name__
    assert health.get(pid).total_successes == 1


def test_sequential_records_failure_on_exception(tmp_path) -> None:
    health = _health()
    r = _retriever(tmp_path, health=health)
    p = _Provider("FailProv", raises=OSError("429 Too Many Requests"))
    r.providers = [p]

    r._search_sequential("query", 5)
    pid = type(p).__name__
    h = health.get(pid)
    assert h.total_failures == 1
    assert h.last_error_type == ProviderErrorType.RATE_LIMIT


def test_sequential_records_failure_on_403(tmp_path) -> None:
    health = _health()
    r = _retriever(tmp_path, health=health)
    p = _Provider("BlockedProv", raises=OSError("403 Forbidden"))
    r.providers = [p]
    r._search_sequential("query", 5)
    assert health.get(type(p).__name__).last_error_type == ProviderErrorType.BLOCKED


# ---------------------------------------------------------------------------
# SERP cache — search()
# ---------------------------------------------------------------------------

def test_cache_hit_skips_providers(tmp_path) -> None:
    cache = _cache(tmp_path)
    cached = [{"title": "Cached Result", "url": "https://cached.com", "snippet": "cached"}]
    cache.set("dive", "cached query", cached)

    r = _retriever(tmp_path, cache=cache)
    p = _Provider("UnusedProvider", results=[{"title": "Fresh", "url": "https://fresh.com", "snippet": "fresh"}])
    r.providers = [p]

    results = r.search("cached query", 5)
    assert p.call_count == 0, "Provider must not be called on cache hit"
    assert results == cached


def test_cache_miss_populates_cache(tmp_path) -> None:
    cache = _cache(tmp_path)
    fresh = [{"title": "Fresh Corp", "url": "https://fresh.com", "snippet": "good content here"}]
    r = _retriever(tmp_path, cache=cache)
    p = _Provider("FreshProvider", results=fresh)
    r.providers = [p]

    # First call — cache miss → hits provider
    results1 = r.search("fresh query", 5)
    assert p.call_count == 1

    # Second call — same query → cache hit, provider not called again
    results2 = r.search("fresh query", 5)
    assert p.call_count == 1, "Provider should not be called again on cache hit"
    assert results1 == results2


def test_cache_key_includes_strategy(tmp_path) -> None:
    cache = _cache(tmp_path)
    dive_results = [{"title": "Dive Result", "url": "https://d.com", "snippet": "content"}]
    cache.set("dive", "same query", dive_results)

    # anchor strategy — different cache key
    r_anchor = RoutedRetriever(
        policy=RetrievalPolicy(), strategy="anchor",
        health=_health(), cache=cache,
    )
    r_anchor.providers = [_Provider("AnchorProv", results=[{"title": "Anchor", "url": "https://a.com", "snippet": "c"}])]
    results = r_anchor.search("same query", 5)
    assert results[0]["title"] == "Anchor", "anchor strategy should not hit dive cache"


def test_empty_result_not_cached(tmp_path) -> None:
    cache = _cache(tmp_path)
    r = _retriever(tmp_path, cache=cache)
    r.providers = [_Provider("EmptyProv", results=[])]

    r.search("empty query", 5)
    assert cache.get("dive", "empty query") is None, "Empty results should not be cached"


# ---------------------------------------------------------------------------
# _classify_error
# ---------------------------------------------------------------------------

def test_classify_rate_limit() -> None:
    assert _classify_error("HTTP Error 429 Too Many Requests") == ProviderErrorType.RATE_LIMIT


def test_classify_blocked() -> None:
    assert _classify_error("403 Forbidden") == ProviderErrorType.BLOCKED


def test_classify_timeout() -> None:
    assert _classify_error("Connection timed out") == ProviderErrorType.TIMEOUT


def test_classify_generic() -> None:
    assert _classify_error("Connection reset by peer") == ProviderErrorType.NETWORK_ERROR


# ---------------------------------------------------------------------------
# _provider_id
# ---------------------------------------------------------------------------

def test_provider_id_uses_class_name() -> None:
    p = _Provider("anything")
    assert _provider_id(p) == "_Provider"
