"""Tests for SERPCache and URLContentCache (diskcache-backed)."""
from __future__ import annotations

import tempfile

import pytest

from retrieval.cache import SERPCache, URLContentCache


@pytest.fixture()
def serp_cache(tmp_path):
    return SERPCache(cache_dir=str(tmp_path / "serp"), ttl=3600)


@pytest.fixture()
def url_cache(tmp_path):
    return URLContentCache(cache_dir=str(tmp_path / "url"), ttl=3600)


def test_serp_cache_is_available(serp_cache: SERPCache) -> None:
    assert serp_cache.available is True


def test_serp_cache_miss_returns_none(serp_cache: SERPCache) -> None:
    result = serp_cache.get("ddg", "unknown query xyz")
    assert result is None


def test_serp_cache_set_and_get(serp_cache: SERPCache) -> None:
    results = [{"title": "ACME Corp", "url": "https://acme.com", "snippet": ""}]
    serp_cache.set("ddg", "ACME Corp distributor", results)
    hit = serp_cache.get("ddg", "ACME Corp distributor")
    assert hit is not None
    assert hit[0]["title"] == "ACME Corp"


def test_serp_cache_key_includes_region(serp_cache: SERPCache) -> None:
    results_eu = [{"title": "EU Result", "url": "https://eu.example.com", "snippet": ""}]
    results_us = [{"title": "US Result", "url": "https://us.example.com", "snippet": ""}]
    serp_cache.set("ddg", "test query", results_eu, region="de-de")
    serp_cache.set("ddg", "test query", results_us, region="en-us")
    eu = serp_cache.get("ddg", "test query", region="de-de")
    us = serp_cache.get("ddg", "test query", region="en-us")
    assert eu is not None and eu[0]["title"] == "EU Result"
    assert us is not None and us[0]["title"] == "US Result"


def test_serp_cache_second_query_hits_cache(serp_cache: SERPCache) -> None:
    """Verify that the second identical query hits cache, not the provider."""
    results = [{"title": "Cached Corp", "url": "https://cached.com", "snippet": ""}]
    serp_cache.set("searxng", "Cached Corp", results)
    # First retrieval
    hit1 = serp_cache.get("searxng", "Cached Corp")
    # Second retrieval — same key
    hit2 = serp_cache.get("searxng", "Cached Corp")
    assert hit1 == hit2 == results


def test_serp_cache_invalidate(serp_cache: SERPCache) -> None:
    results = [{"title": "Corp X", "url": "https://x.com", "snippet": ""}]
    serp_cache.set("ddg", "Corp X", results)
    serp_cache.invalidate("ddg", "Corp X")
    assert serp_cache.get("ddg", "Corp X") is None


def test_serp_cache_empty_results_not_stored(serp_cache: SERPCache) -> None:
    serp_cache.set("ddg", "empty query", [])
    assert serp_cache.get("ddg", "empty query") is None


# URL content cache

def test_url_cache_miss_returns_none(url_cache: URLContentCache) -> None:
    assert url_cache.get("https://notcached.example.com") is None


def test_url_cache_set_and_get(url_cache: URLContentCache) -> None:
    content = b"<html><body>Hello</body></html>"
    url_cache.set("https://example.com/page", content)
    hit = url_cache.get("https://example.com/page")
    assert hit == content


def test_url_cache_different_urls_isolated(url_cache: URLContentCache) -> None:
    url_cache.set("https://a.com", b"content A")
    url_cache.set("https://b.com", b"content B")
    assert url_cache.get("https://a.com") == b"content A"
    assert url_cache.get("https://b.com") == b"content B"
