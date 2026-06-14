"""Tests for seed_urls mechanism: seed_fetcher + KeywordGraph.seed_from_terms + controller bootstrap."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from core.keyword_graph import KeywordGraph
from core.types import Intent
from salva_core.schemas import RetrievalPolicy


# ---------------------------------------------------------------------------
# seed_fetcher
# ---------------------------------------------------------------------------

def _no_obscura(sf):
    """Context manager that disables Obscura binary detection in seed_fetcher tests."""
    return patch.object(sf, "_obscura_binary", return_value=None)


def test_fetch_entity_names_returns_list_items() -> None:
    html = b"""<html><body>
    <ul>
      <li>GIGABYTE Technology</li>
      <li>MSI International</li>
      <li><a href="#">ASUS Global</a></li>
    </ul>
    </body></html>"""
    import retrieval.seed_fetcher as sf
    with _no_obscura(sf), patch.object(sf, "http_get", return_value=html):
        names = sf.fetch_entity_names("https://example.com/list", RetrievalPolicy())
    assert "GIGABYTE Technology" in names
    assert "MSI International" in names


def test_fetch_entity_names_filters_short_strings() -> None:
    html = b"<html><body><ul><li>OK Corp</li><li>x</li><li>ab</li></ul></body></html>"
    import retrieval.seed_fetcher as sf
    with _no_obscura(sf), patch.object(sf, "http_get", return_value=html):
        names = sf.fetch_entity_names("https://example.com", RetrievalPolicy())
    # "x" and "ab" are too short (< 3 chars)
    assert "x" not in names
    assert "ab" not in names
    assert "OK Corp" in names


def test_fetch_entity_names_deduplicates() -> None:
    html = b"<html><body><ul><li>ACME Corp</li><li>ACME Corp</li></ul></body></html>"
    import retrieval.seed_fetcher as sf
    with _no_obscura(sf), patch.object(sf, "http_get", return_value=html):
        names = sf.fetch_entity_names("https://example.com", RetrievalPolicy())
    assert names.count("ACME Corp") == 1


def test_fetch_entity_names_returns_empty_on_error() -> None:
    import retrieval.seed_fetcher as sf
    with _no_obscura(sf), patch.object(sf, "http_get", side_effect=OSError("timeout")):
        names = sf.fetch_entity_names("https://example.com", RetrievalPolicy())
    assert names == []


def test_fetch_entity_names_uses_obscura_text_when_available() -> None:
    """When Obscura returns sufficient text, use it instead of http_get."""
    import retrieval.seed_fetcher as sf
    obscura_text = "GIGABYTE Technology\nMSI International\nASUS Global\nASRock Holdings\n"
    with patch.object(sf, "_obscura_binary", return_value="/usr/bin/obscura"), \
         patch.object(sf, "_obscura_fetch_text", return_value=obscura_text) as mock_obs, \
         patch.object(sf, "http_get") as mock_get:
        names = sf.fetch_entity_names("https://js-heavy.example.com/dir", RetrievalPolicy())
    mock_obs.assert_called_once()
    mock_get.assert_not_called()
    assert "GIGABYTE Technology" in names
    assert "MSI International" in names


# ---------------------------------------------------------------------------
# KeywordGraph.seed_from_terms
# ---------------------------------------------------------------------------

def _intent(**kw) -> Intent:
    return Intent(domain="test", primary_terms=["test"], **kw)


def test_seed_from_terms_injects_new_nodes() -> None:
    graph = KeywordGraph(intent=_intent())
    injected = graph.seed_from_terms(["GIGABYTE", "MSI", "ASUS"])
    assert injected == 3
    assert "GIGABYTE" in graph.nodes
    assert graph.nodes["GIGABYTE"].node_type == "seed"
    assert graph.nodes["GIGABYTE"].weight == 0.9


def test_seed_from_terms_skips_existing_nodes() -> None:
    graph = KeywordGraph(intent=_intent())
    # "test" is already a primary node from bootstrap
    injected = graph.seed_from_terms(["test", "NewCorp"])
    assert injected == 1
    # primary type preserved for "test"
    assert graph.nodes["test"].node_type == "primary"


def test_seed_from_terms_skips_blank_strings() -> None:
    graph = KeywordGraph(intent=_intent())
    injected = graph.seed_from_terms(["", "  ", "ValidCorp"])
    assert injected == 1


def test_seed_from_terms_custom_weight_and_type() -> None:
    graph = KeywordGraph(intent=_intent())
    graph.seed_from_terms(["SpecialCorp"], node_type="memory", weight=0.5)
    assert graph.nodes["SpecialCorp"].node_type == "memory"
    assert graph.nodes["SpecialCorp"].weight == 0.5


# ---------------------------------------------------------------------------
# Controller bootstrap integration
# ---------------------------------------------------------------------------

def _make_controller(seed_urls: list[str]):
    from processing.dedup import MemoryDeduplicator
    from processing.extractor import BaseExtractor
    from processing.scorer import QualificationScorer
    from retrieval.router import RoutedRetriever
    from core.controller import SalvaController

    policy = RetrievalPolicy()
    intent = _intent(seed_urls=seed_urls)
    retriever = RoutedRetriever(policy=policy, strategy="dive")
    return SalvaController(
        intent=intent,
        retrievers={"dive": retriever},
        extractor=BaseExtractor(),
        deduplicator=MemoryDeduplicator(),
        scorer=QualificationScorer(),
        keyword_graph=KeywordGraph(intent=intent),
    )


def test_controller_bootstrap_injects_names_from_seed_urls() -> None:
    html = b"<html><body><ul><li>Exhibitor Alpha</li><li>Exhibitor Beta</li></ul></body></html>"
    import retrieval.seed_fetcher as sf
    with _no_obscura(sf), patch.object(sf, "http_get", return_value=html):
        ctrl = _make_controller(seed_urls=["https://example.com/exhibitors"])
        ctrl._bootstrap_seed_urls()
    assert "Exhibitor Alpha" in ctrl.graph.nodes
    assert "Exhibitor Beta" in ctrl.graph.nodes


def test_controller_bootstrap_skips_when_no_seed_urls() -> None:
    ctrl = _make_controller(seed_urls=[])
    import retrieval.seed_fetcher as sf
    with _no_obscura(sf), patch.object(sf, "http_get") as mock_get:
        ctrl._bootstrap_seed_urls()
    mock_get.assert_not_called()


def test_intent_seed_urls_field_exists() -> None:
    i = Intent(domain="test", primary_terms=["x"], seed_urls=["https://a.com", "https://b.com"])
    assert i.seed_urls == ["https://a.com", "https://b.com"]


def test_intent_seed_urls_defaults_empty() -> None:
    i = Intent(domain="test", primary_terms=["x"])
    assert i.seed_urls == []
