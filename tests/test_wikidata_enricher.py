"""Unit tests for WikidataEnricher — all mocked, no live network."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from enrichment.entity_enricher import WikidataEnricher, WikidataEntityMeta, _enabled


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_response(search_results: list[dict]) -> MagicMock:
    raw = json.dumps({"search": search_results}).encode()
    resp = MagicMock()
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    resp.read = MagicMock(return_value=raw)
    # json.load reads from file-like; patch json.load separately
    return resp


def _patch_urlopen(search_results: list[dict]):
    payload = {"search": search_results}

    class _FakeResp:
        def __enter__(self):
            return self
        def __exit__(self, *_):
            pass
        def read(self):
            return json.dumps(payload).encode()

    return patch("urllib.request.urlopen", return_value=_FakeResp())


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_enrich_returns_meta_on_hit() -> None:
    hit = {"id": "Q95", "label": "Google", "description": "American technology company"}
    with _patch_urlopen([hit]):
        meta = WikidataEnricher().enrich("Google")

    assert meta is not None
    assert meta.qid == "Q95"
    assert meta.label == "Google"
    assert "technology" in meta.description


def test_enrich_returns_none_on_empty_results() -> None:
    with _patch_urlopen([]):
        meta = WikidataEnricher().enrich("NonExistentXYZ")
    assert meta is None


def test_enrich_returns_none_on_network_error() -> None:
    with patch("urllib.request.urlopen", side_effect=OSError("timeout")):
        meta = WikidataEnricher().enrich("TSMC")
    assert meta is None


def test_enrich_skips_when_disabled(monkeypatch) -> None:
    monkeypatch.setenv("WIKIDATA_ENABLED", "false")
    called = []
    with patch("urllib.request.urlopen", side_effect=lambda *a, **k: called.append(1)):
        meta = WikidataEnricher().enrich("Google")
    assert meta is None
    assert not called


def test_enrich_skips_empty_name() -> None:
    called = []
    with patch("urllib.request.urlopen", side_effect=lambda *a, **k: called.append(1)):
        meta = WikidataEnricher().enrich("   ")
    assert meta is None
    assert not called


def test_enrich_strips_whitespace_from_fields() -> None:
    hit = {"id": " Q95 ", "label": " Google ", "description": " tech "}
    with _patch_urlopen([hit]):
        meta = WikidataEnricher().enrich("Google")
    assert meta is not None
    assert meta.qid == "Q95"
    assert meta.label == "Google"
    assert meta.description == "tech"


def test_enrich_returns_none_when_qid_missing() -> None:
    hit = {"id": "", "label": "Google", "description": "tech co"}
    with _patch_urlopen([hit]):
        meta = WikidataEnricher().enrich("Google")
    assert meta is None


def test_enrich_returns_none_when_label_missing() -> None:
    hit = {"id": "Q95", "label": "", "description": "tech co"}
    with _patch_urlopen([hit]):
        meta = WikidataEnricher().enrich("Google")
    assert meta is None


def test_meta_is_frozen() -> None:
    meta = WikidataEntityMeta(qid="Q95", label="Google", description="tech")
    with pytest.raises((AttributeError, TypeError)):
        meta.qid = "Q1"  # type: ignore[misc]


def test_custom_base_url_is_used() -> None:
    hit = {"id": "Q1", "label": "Test", "description": "desc"}
    captured_url: list[str] = []

    class _FakeResp:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def read(self): return json.dumps({"search": [hit]}).encode()

    def _fake_open(req, timeout=None):
        captured_url.append(req.full_url)
        return _FakeResp()

    with patch("urllib.request.urlopen", side_effect=_fake_open):
        WikidataEnricher(base_url="https://my-mirror.example").enrich("Test")

    assert captured_url and "my-mirror.example" in captured_url[0]
