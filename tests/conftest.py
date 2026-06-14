"""Shared pytest fixtures for Salva test suite."""
from __future__ import annotations

import pytest

import retrieval.cache as _cache_mod
from retrieval.cache import SERPCache


@pytest.fixture(autouse=True)
def _isolated_serp_cache(tmp_path, monkeypatch):
    """Redirect the module-level SERP cache singleton to a per-test tmpdir.

    Prevents cross-test result pollution when RoutedRetriever falls back to
    get_serp_cache() (i.e., no explicit cache= argument was passed).
    Tests that inject their own SERPCache instance are unaffected.
    """
    fresh = SERPCache(cache_dir=str(tmp_path / "serp_cache"), ttl=3600)
    monkeypatch.setattr(_cache_mod, "_serp_cache", fresh)
