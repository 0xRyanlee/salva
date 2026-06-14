"""Tests for MarginaliaRetriever."""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

import retrieval.sources.marginalia as marginalia_mod
from retrieval.sources.marginalia import MarginaliaRetriever, _marginalia_enabled
from salva_core.schemas import RetrievalPolicy


def _policy(**kw) -> RetrievalPolicy:
    return RetrievalPolicy(**kw)


def _api_payload(items: list[dict]) -> bytes:
    return json.dumps({"results": items, "page": 1, "pages": 1}).encode()


def test_enabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MARGINALIA_ENABLED", raising=False)
    assert _marginalia_enabled() is True


def test_disabled_via_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MARGINALIA_ENABLED", "false")
    assert _marginalia_enabled() is False


def test_search_returns_empty_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(marginalia_mod, "_marginalia_enabled", lambda: False)
    r = MarginaliaRetriever(policy=_policy())
    assert r.search("test") == []
    assert r.last_attempts == []


def test_search_maps_fields() -> None:
    payload = _api_payload([
        {"url": "https://example.com/a", "title": "Example A", "description": "snippet a", "quality": 0.9},
        {"url": "https://example.com/b", "title": "Example B", "description": "", "quality": 0.5},
        {"url": "", "title": "No URL"},
    ])
    with patch.object(marginalia_mod, "http_get", return_value=payload):
        r = MarginaliaRetriever(policy=_policy())
        results = r.search("test", n=10)

    assert len(results) == 2
    assert results[0]["url"] == "https://example.com/a"
    assert results[0]["title"] == "Example A"
    assert results[0]["snippet"] == "snippet a"
    assert results[0]["engine"] == "marginalia"
    assert results[0]["quality"] == 0.9


def test_search_respects_n_limit() -> None:
    items = [{"url": f"https://example.com/{i}", "title": f"Item {i}", "description": f"d{i}"} for i in range(20)]
    payload = _api_payload(items)
    with patch.object(marginalia_mod, "http_get", return_value=payload):
        r = MarginaliaRetriever(policy=_policy())
        results = r.search("test", n=5)
    assert len(results) == 5


def test_search_records_attempt_on_success() -> None:
    payload = _api_payload([{"url": "https://x.com", "title": "X", "description": "d"}])
    with patch.object(marginalia_mod, "http_get", return_value=payload):
        r = MarginaliaRetriever(policy=_policy())
        results = r.search("test", n=5)
    assert len(r.last_attempts) == 1
    assert r.last_attempts[0].succeeded is True
    assert r.last_attempts[0].provider == "marginalia"


def test_search_returns_empty_on_network_error() -> None:
    def _boom(*a, **kw): raise OSError("timeout")
    with patch.object(marginalia_mod, "http_get", side_effect=_boom):
        r = MarginaliaRetriever(policy=_policy())
        results = r.search("test", n=5)
    assert results == []
    # last_attempts has the error entry from _fetch_page + the outer append
    assert any(a.succeeded is False for a in r.last_attempts)


def test_registry_includes_marginalia() -> None:
    from retrieval.registry import available_provider_kinds
    assert "marginalia" in available_provider_kinds()


def test_registry_default_chain_includes_marginalia() -> None:
    from retrieval.registry import build_provider_chain
    chain = build_provider_chain(_policy(), "anchor")
    names = [type(p).__name__ for p in chain]
    assert "MarginaliaRetriever" in names
