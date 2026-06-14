"""Tests for GLEIF resolver — mocked network, no live calls."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from salva_core.resolvers.gleif import GleifMatch, gleif_lookup, gleif_resolve


def _make_response(items: list[dict]) -> MagicMock:
    """Build a mock urlopen context manager returning given items."""
    payload = json.dumps({"data": items}).encode()
    mock_resp = MagicMock()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_resp.read = lambda: payload
    # json.load reads from the file-like object
    mock_resp.read = lambda: payload
    # urllib.request.urlopen returns a file-like; json.load calls read()
    return mock_resp


def _item(name: str, lei: str) -> dict:
    return {
        "type": "fuzzycompletions",
        "attributes": {"value": name},
        "relationships": {
            "lei-records": {
                "data": {"type": "lei-records", "id": lei},
                "links": {"related": f"https://api.gleif.org/api/v1/lei-records/{lei}"},
            }
        },
    }


# ---------------------------------------------------------------------------
# gleif_lookup
# ---------------------------------------------------------------------------

def test_gleif_lookup_returns_matches() -> None:
    items = [_item("GIGABYTE Technology Co., Ltd.", "ABC123DEF456GHI78901")]
    resp_bytes = json.dumps({"data": items}).encode()

    import urllib.request as _urllib
    mock_ctx = MagicMock()
    mock_ctx.__enter__ = lambda s: MagicMock(read=lambda: resp_bytes, **{"__iter__": iter})
    mock_ctx.__exit__ = MagicMock(return_value=False)

    with patch("salva_core.resolvers.gleif.urllib.request.urlopen", return_value=mock_ctx) as mock_open:
        # json.load needs a file-like — patch json.load instead
        with patch("salva_core.resolvers.gleif.json.load", return_value={"data": items}):
            results = gleif_lookup("GIGABYTE", top_k=3)

    assert len(results) == 1
    assert isinstance(results[0], GleifMatch)
    assert results[0].legal_name == "GIGABYTE Technology Co., Ltd."
    assert results[0].lei == "ABC123DEF456GHI78901"


def test_gleif_lookup_top_k_limits_results() -> None:
    items = [_item(f"Company {i}", f"LEI{i:017d}") for i in range(5)]

    with patch("salva_core.resolvers.gleif.json.load", return_value={"data": items}):
        with patch("salva_core.resolvers.gleif.urllib.request.urlopen") as mock_open:
            mock_open.return_value.__enter__ = lambda s: s
            mock_open.return_value.__exit__ = MagicMock(return_value=False)
            results = gleif_lookup("Company", top_k=2)

    assert len(results) == 2


def test_gleif_lookup_skips_items_missing_lei() -> None:
    items = [
        {"type": "fuzzycompletions", "attributes": {"value": "Valid Corp"},
         "relationships": {"lei-records": {"data": {"type": "lei-records", "id": "LEI00000000000000001"}}}},
        {"type": "fuzzycompletions", "attributes": {"value": "No LEI"},
         "relationships": {"lei-records": {"data": {"type": "lei-records", "id": ""}}}},
    ]
    with patch("salva_core.resolvers.gleif.json.load", return_value={"data": items}):
        with patch("salva_core.resolvers.gleif.urllib.request.urlopen") as mock_open:
            mock_open.return_value.__enter__ = lambda s: s
            mock_open.return_value.__exit__ = MagicMock(return_value=False)
            results = gleif_lookup("test")

    assert len(results) == 1
    assert results[0].legal_name == "Valid Corp"


def test_gleif_lookup_returns_empty_on_network_error() -> None:
    with patch("salva_core.resolvers.gleif.urllib.request.urlopen", side_effect=OSError("timeout")):
        results = gleif_lookup("GIGABYTE")
    assert results == []


def test_gleif_lookup_returns_empty_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GLEIF_ENABLED", "false")
    import salva_core.resolvers.gleif as gleif_mod
    # _gleif_enabled() reads env at call time
    with patch.object(gleif_mod, "_gleif_enabled", return_value=False):
        results = gleif_lookup("anything")
    assert results == []


def test_gleif_lookup_returns_empty_for_blank_name() -> None:
    results = gleif_lookup("  ")
    assert results == []


# ---------------------------------------------------------------------------
# gleif_resolve
# ---------------------------------------------------------------------------

def test_gleif_resolve_returns_canonical_name() -> None:
    items = [_item("MSI International Ltd.", "MSI0000000000000001")]
    with patch("salva_core.resolvers.gleif.json.load", return_value={"data": items}):
        with patch("salva_core.resolvers.gleif.urllib.request.urlopen") as mock_open:
            mock_open.return_value.__enter__ = lambda s: s
            mock_open.return_value.__exit__ = MagicMock(return_value=False)
            name = gleif_resolve("MSI")
    assert name == "MSI International Ltd."


def test_gleif_resolve_returns_none_when_no_match() -> None:
    with patch("salva_core.resolvers.gleif.urllib.request.urlopen", side_effect=OSError("no network")):
        name = gleif_resolve("NonExistentCompany12345")
    assert name is None
