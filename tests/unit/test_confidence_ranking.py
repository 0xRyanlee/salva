import os

import pytest

os.environ.setdefault("SALVA_SEMANTIC_VECTOR_BACKEND", "hybrid_hash")

from core.types import Intent, UnifiedResult
from processing.confidence import (
    RankingWeights,
    RetrievalProvenance,
    corroboration_saturation,
    rank_candidates,
    registered_domain,
)


def _result(url: str, title: str = "Acme Corp official site", desc: str = "widgets") -> UnifiedResult:
    return UnifiedResult(source_name="ddgs", source_url=url, title=title, description=desc)


def _intent() -> Intent:
    return Intent(domain="companies", primary_terms=["Acme", "widgets"], region="Germany")


def test_registered_domain_strips_www():
    assert registered_domain("https://www.acme.com/x") == "acme.com"
    assert registered_domain("https://acme.com/x") == "acme.com"
    assert registered_domain("") == ""


def test_corroboration_lifts_multi_query_source_over_single_query():
    # Two candidates with identical content -> only corroboration differs.
    strong = _result("https://acme.com/a")
    weak = _result("https://other.com/b")

    prov = RetrievalProvenance()
    # strong surfaced by three distinct query formulations, weak by one.
    prov.observe("https://acme.com/a", "ddgs", "dive", "acme widgets")
    prov.observe("https://acme.com/a", "ddgs", "anchor", "acme germany")
    prov.observe("https://acme.com/a", "ddgs", "radar", "acme supplier")
    prov.observe("https://other.com/b", "ddgs", "dive", "acme widgets")

    ranked = rank_candidates([weak, strong], _intent(), prov)
    order = [r.source_url for r, _, _ in ranked]
    assert order[0] == "https://acme.com/a"
    assert strong.confidence > weak.confidence


def test_single_query_support_has_zero_corroboration():
    r = _result("https://acme.com/a")
    prov = RetrievalProvenance()
    prov.observe("https://acme.com/a", "ddgs", "dive", "q1")
    ranked = rank_candidates([r], _intent(), prov, weights=RankingWeights(content=0.0, corroboration=1.0, source_trust=0.0))
    _, confidence, signals = ranked[0]
    assert signals.query_support == 1
    assert signals.corroboration == 0.0
    assert confidence == 0.0


def test_rank_assigns_confidence_and_sorts_descending():
    a = _result("https://acme.com/a")
    b = _result("https://acme.com/b")
    prov = RetrievalProvenance()
    prov.observe("https://acme.com/a", "ddgs", "dive", "q1")
    prov.observe("https://acme.com/a", "ddgs", "anchor", "q2")
    prov.observe("https://acme.com/b", "ddgs", "dive", "q1")
    ranked = rank_candidates([a, b], _intent(), prov)
    confidences = [c for _, c, _ in ranked]
    assert confidences == sorted(confidences, reverse=True)
    assert a.confidence >= 0.0 and b.confidence >= 0.0


def test_corroboration_saturation_reports_fraction_with_support():
    a = _result("https://acme.com/a")
    b = _result("https://other.com/b")
    prov = RetrievalProvenance()
    prov.observe("https://acme.com/a", "ddgs", "dive", "q1")
    prov.observe("https://acme.com/a", "ddgs", "anchor", "q2")
    prov.observe("https://other.com/b", "ddgs", "dive", "q1")
    ranked = rank_candidates([a, b], _intent(), prov)
    assert corroboration_saturation(ranked) == pytest.approx(0.5)
    assert corroboration_saturation([]) == 0.0


def test_provider_diversity_counts_distinct_providers():
    r = _result("https://acme.com/a")
    prov = RetrievalProvenance()
    prov.observe("https://acme.com/a", "ddgs", "dive", "q1")
    prov.observe("https://acme.com/a", "searxng", "dive", "q1")
    ranked = rank_candidates([r], _intent(), prov)
    _, _, signals = ranked[0]
    assert signals.provider_diversity == 2
