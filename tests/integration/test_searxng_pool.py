"""Tests for PublicSearXNGPool with health gating and circuit breaker."""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from retrieval.health import ProviderErrorType, ProviderHealthRegistry
from retrieval.sources.searxng_pool import PublicSearXNGPool
from salva_core.schemas import RetrievalPolicy


_GOOD_RESPONSE = json.dumps({
    "results": [
        {"title": "ACME Corp", "url": "https://acme.com", "content": "ACME is a company"},
        {"title": "Beta Ltd",  "url": "https://beta.com", "content": "Beta Ltd overview"},
    ]
}).encode()

_EMPTY_RESPONSE = json.dumps({"results": []}).encode()


def _pool(instances=None) -> tuple[PublicSearXNGPool, ProviderHealthRegistry]:
    health = ProviderHealthRegistry()
    with patch("retrieval.sources.searxng_pool._load_instances",
               return_value=instances or [{"url": "https://test-searxng.example.com", "region": "eu", "enabled": True}]):
        pool = PublicSearXNGPool(RetrievalPolicy(), health=health)
    return pool, health


def test_search_returns_results_on_success() -> None:
    pool, _ = _pool()
    with patch("retrieval.sources.searxng_pool.http_get", return_value=_GOOD_RESPONSE):
        results = pool.search("ACME Corp distributor", n=10)
    assert len(results) == 2
    assert results[0]["title"] == "ACME Corp"
    assert results[0]["engine"] == "searxng_pool"


def test_search_records_success_in_health() -> None:
    pool, health = _pool()
    pid = "searxng_pool:https://test-searxng.example.com"
    with patch("retrieval.sources.searxng_pool.http_get", return_value=_GOOD_RESPONSE):
        pool.search("test query")
    assert health.get(pid).total_successes == 1


def test_search_records_rate_limit_failure() -> None:
    pool, health = _pool()
    pid = "searxng_pool:https://test-searxng.example.com"
    with patch("retrieval.sources.searxng_pool.http_get", side_effect=OSError("429 Too Many Requests")):
        results = pool.search("test query")
    assert results == []
    h = health.get(pid)
    assert h.total_failures == 1
    assert h.last_error_type == ProviderErrorType.RATE_LIMIT


def test_search_records_blocked_failure() -> None:
    pool, health = _pool()
    pid = "searxng_pool:https://test-searxng.example.com"
    with patch("retrieval.sources.searxng_pool.http_get", side_effect=OSError("403 Forbidden")):
        pool.search("test query")
    h = health.get(pid)
    assert h.last_error_type == ProviderErrorType.BLOCKED


def test_search_skips_instance_in_cooldown() -> None:
    pool, health = _pool()
    pid = "searxng_pool:https://test-searxng.example.com"
    # Trip circuit breaker
    for _ in range(3):
        health.record_failure(pid, ProviderErrorType.BLOCKED)
    assert not health.is_usable(pid)
    with patch("retrieval.sources.searxng_pool.http_get") as mock_http:
        results = pool.search("test query")
    mock_http.assert_not_called()
    assert results == []


def test_disabled_instance_excluded() -> None:
    instances = [
        {"url": "https://disabled.example.com", "region": "eu", "enabled": False},
        {"url": "https://enabled.example.com",  "region": "eu", "enabled": True},
    ]
    with patch("retrieval.sources.searxng_pool._load_instances", return_value=instances):
        pool = PublicSearXNGPool(RetrievalPolicy())
    urls = [i["url"] for i in pool._instances]
    assert "https://disabled.example.com" not in urls
    assert "https://enabled.example.com" in urls


def test_search_respects_max_tries() -> None:
    """Should try at most _MAX_TRIES_PER_QUERY instances."""
    instances = [
        {"url": f"https://inst{i}.example.com", "region": "eu", "enabled": True}
        for i in range(5)
    ]
    call_count = 0

    def _fail(url, **kw):
        nonlocal call_count
        call_count += 1
        raise OSError("timeout")

    with patch("retrieval.sources.searxng_pool._load_instances", return_value=instances):
        pool = PublicSearXNGPool(RetrievalPolicy())
    with patch("retrieval.sources.searxng_pool.http_get", side_effect=_fail):
        pool.search("test query")
    # Should not try all 5 instances — capped at _MAX_TRIES_PER_QUERY
    from retrieval.sources.searxng_pool import _MAX_TRIES_PER_QUERY
    assert call_count <= _MAX_TRIES_PER_QUERY
