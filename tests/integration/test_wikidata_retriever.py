"""Tests for WikidataRetriever."""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

import retrieval.sources.wikidata as wikidata_mod
from retrieval.sources.wikidata import WikidataRetriever, _wikidata_enabled
from salva_core.schemas import RetrievalPolicy, RetrievalProviderConfig


def _policy(**kw) -> RetrievalPolicy:
    return RetrievalPolicy(**kw)


def _api_payload(items: list[dict]) -> bytes:
    return json.dumps({"searchinfo": {"search": "q"}, "search": items}).encode()


def test_enabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WIKIDATA_ENABLED", raising=False)
    assert _wikidata_enabled() is True


def test_disabled_via_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WIKIDATA_ENABLED", "false")
    assert _wikidata_enabled() is False


def test_search_returns_empty_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(wikidata_mod, "_wikidata_enabled", lambda: False)
    r = WikidataRetriever(policy=_policy())
    assert r.search("test") == []
    assert r.last_attempts == []


def test_search_maps_fields_and_resolves_protocol_relative_url() -> None:
    payload = _api_payload([
        {
            "id": "Q713418",
            "url": "//www.wikidata.org/wiki/Q713418",
            "label": "TSMC",
            "description": "semiconductor foundry company headquartered in Taiwan",
        },
        {"id": "Q0", "url": "", "label": "No URL"},
    ])
    with patch.object(wikidata_mod, "http_get", return_value=payload):
        r = WikidataRetriever(policy=_policy())
        results = r.search("台積電", n=10)

    assert len(results) == 1
    assert results[0]["url"] == "https://www.wikidata.org/wiki/Q713418"
    assert results[0]["title"] == "TSMC"
    assert results[0]["snippet"] == "semiconductor foundry company headquartered in Taiwan"
    assert results[0]["engine"] == "wikidata"
    assert results[0]["wikidata_qid"] == "Q713418"


def test_search_respects_n_limit() -> None:
    items = [
        {
            "id": f"Q{i}", "url": f"//www.wikidata.org/wiki/Q{i}",
            "label": f"Item {i}", "description": f"d{i}",
        }
        for i in range(20)
    ]
    payload = _api_payload(items)
    with patch.object(wikidata_mod, "http_get", return_value=payload):
        r = WikidataRetriever(policy=_policy())
        results = r.search("test", n=5)
    assert len(results) == 5


def test_search_records_attempt_on_success() -> None:
    payload = _api_payload([
        {"id": "Q1", "url": "//www.wikidata.org/wiki/Q1", "label": "X", "description": "d"},
    ])
    with patch.object(wikidata_mod, "http_get", return_value=payload):
        r = WikidataRetriever(policy=_policy())
        r.search("test", n=5)
    assert len(r.last_attempts) == 1
    assert r.last_attempts[0].succeeded is True
    assert r.last_attempts[0].provider == "wikidata"


def test_search_returns_empty_on_network_error() -> None:
    def _boom(*a, **kw):
        raise OSError("timeout")
    with patch.object(wikidata_mod, "http_get", side_effect=_boom):
        r = WikidataRetriever(policy=_policy())
        results = r.search("test", n=5)
    assert results == []
    assert len(r.last_attempts) == 1
    assert r.last_attempts[0].succeeded is False


def test_search_returns_empty_on_malformed_json() -> None:
    with patch.object(wikidata_mod, "http_get", return_value=b"not json"):
        r = WikidataRetriever(policy=_policy())
        results = r.search("test", n=5)
    assert results == []
    assert r.last_attempts[0].succeeded is False


def test_registry_includes_wikidata() -> None:
    from retrieval.registry import available_provider_kinds
    assert "wikidata" in available_provider_kinds()


def test_registry_default_chain_excludes_wikidata() -> None:
    """Opt-in only per this card's guardrail -- must not silently join the
    default chain and add an external dependency to every query."""
    from retrieval.registry import build_provider_chain
    chain = build_provider_chain(_policy(), "anchor")
    names = [type(p).__name__ for p in chain]
    assert "WikidataRetriever" not in names


def test_registry_explicit_opt_in_builds_wikidata() -> None:
    from retrieval.registry import build_provider_chain
    policy = _policy(providers=[RetrievalProviderConfig(kind="wikidata")])
    chain = build_provider_chain(policy, "anchor")
    names = [type(p).__name__ for p in chain]
    assert "WikidataRetriever" in names
