"""Tests for DDGSRetriever — covers graceful degradation and result mapping."""
from __future__ import annotations

import sys
from types import ModuleType
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from retrieval.sources.ddgs_retriever import DDGSRetriever, _is_ddgs_available
from salva_core.schemas import RetrievalPolicy


def _make_policy(**kwargs: Any) -> RetrievalPolicy:
    return RetrievalPolicy(**kwargs)


# ---------------------------------------------------------------------------
# Availability probe
# ---------------------------------------------------------------------------

def test_is_ddgs_available_with_package_installed() -> None:
    # ddgs is installed in the test venv; probe should return True
    assert _is_ddgs_available() is True


def test_is_ddgs_available_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    import retrieval.sources.ddgs_retriever as mod
    monkeypatch.setattr(mod, "_DDGS_AVAILABLE", None)

    original_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__  # type: ignore[attr-defined]

    def _block_ddgs(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "ddgs":
            raise ImportError("ddgs not installed")
        return original_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=_block_ddgs):
        monkeypatch.setattr(mod, "_DDGS_AVAILABLE", None)
        result = mod._is_ddgs_available()
    assert result is False
    monkeypatch.setattr(mod, "_DDGS_AVAILABLE", None)  # reset for other tests


# ---------------------------------------------------------------------------
# Search result mapping
# ---------------------------------------------------------------------------

def test_search_maps_href_to_url() -> None:
    raw = [
        {"href": "https://example.com/a", "title": "Example A", "body": "snippet a"},
        {"href": "https://example.com/b", "title": "Example B", "body": ""},
    ]
    policy = _make_policy()
    retriever = DDGSRetriever(policy=policy)

    mock_ddgs = MagicMock()
    mock_ddgs.__enter__ = lambda s: mock_ddgs
    mock_ddgs.__exit__ = MagicMock(return_value=False)
    mock_ddgs.text.return_value = raw

    with patch("retrieval.sources.ddgs_retriever.DDGS", return_value=mock_ddgs):
        results = retriever.search("test query", n=10)

    assert len(results) == 2
    assert results[0]["url"] == "https://example.com/a"
    assert results[0]["title"] == "Example A"
    assert results[0]["snippet"] == "snippet a"
    assert results[1]["url"] == "https://example.com/b"


def test_search_skips_items_with_no_url() -> None:
    raw = [
        {"href": "", "title": "No URL", "body": "text"},
        {"title": "Also no URL"},
        {"href": "https://valid.com", "title": "Valid", "body": "ok"},
    ]
    policy = _make_policy()
    retriever = DDGSRetriever(policy=policy)

    mock_ddgs = MagicMock()
    mock_ddgs.__enter__ = lambda s: mock_ddgs
    mock_ddgs.__exit__ = MagicMock(return_value=False)
    mock_ddgs.text.return_value = raw

    with patch("retrieval.sources.ddgs_retriever.DDGS", return_value=mock_ddgs):
        results = retriever.search("q", n=10)

    assert len(results) == 1
    assert results[0]["url"] == "https://valid.com"


def test_search_passes_region_hint() -> None:
    policy = _make_policy(region_hint="de-de")
    retriever = DDGSRetriever(policy=policy)

    mock_ddgs = MagicMock()
    mock_ddgs.__enter__ = lambda s: mock_ddgs
    mock_ddgs.__exit__ = MagicMock(return_value=False)
    mock_ddgs.text.return_value = []

    with patch("retrieval.sources.ddgs_retriever.DDGS", return_value=mock_ddgs):
        retriever.search("q", n=5)

    call_kwargs = mock_ddgs.text.call_args
    assert call_kwargs.kwargs.get("region") == "de-de"


def test_search_uses_wt_wt_when_no_region_hint() -> None:
    policy = _make_policy()
    retriever = DDGSRetriever(policy=policy)

    mock_ddgs = MagicMock()
    mock_ddgs.__enter__ = lambda s: mock_ddgs
    mock_ddgs.__exit__ = MagicMock(return_value=False)
    mock_ddgs.text.return_value = []

    with patch("retrieval.sources.ddgs_retriever.DDGS", return_value=mock_ddgs):
        retriever.search("q", n=5)

    call_kwargs = mock_ddgs.text.call_args
    assert call_kwargs.kwargs.get("region") == "wt-wt"


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

def test_search_returns_empty_on_exception() -> None:
    policy = _make_policy()
    retriever = DDGSRetriever(policy=policy)

    mock_ddgs = MagicMock()
    mock_ddgs.__enter__ = lambda s: mock_ddgs
    mock_ddgs.__exit__ = MagicMock(return_value=False)
    mock_ddgs.text.side_effect = RuntimeError("rate limited")

    with patch("retrieval.sources.ddgs_retriever.DDGS", return_value=mock_ddgs):
        results = retriever.search("q", n=5)

    assert results == []
    assert len(retriever.last_attempts) == 1
    assert retriever.last_attempts[0].succeeded is False
    assert "rate limited" in (retriever.last_attempts[0].error or "")


def test_search_returns_empty_when_ddgs_unavailable() -> None:
    import retrieval.sources.ddgs_retriever as mod

    policy = _make_policy()
    retriever = DDGSRetriever(policy=policy)

    with patch.object(mod, "_DDGS_AVAILABLE", False):
        results = retriever.search("q", n=5)

    assert results == []
    assert retriever.last_attempts == []


# ---------------------------------------------------------------------------
# Registry integration
# ---------------------------------------------------------------------------

def test_registry_includes_ddgs_when_available() -> None:
    from retrieval.registry import available_provider_kinds
    kinds = available_provider_kinds()
    assert "ddgs" in kinds


def test_registry_build_default_chain_uses_ddgs() -> None:
    from retrieval.registry import build_provider_chain
    policy = _make_policy()
    chain = build_provider_chain(policy, "dive")
    provider_types = [type(p).__name__ for p in chain]
    assert "DDGSRetriever" in provider_types
    assert "DDGHTMLRetriever" not in provider_types
