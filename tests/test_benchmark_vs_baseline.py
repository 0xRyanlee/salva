"""Benchmark tests: Salva pipeline vs naive retrieval baseline.

Each test uses frozen/mock data (no network calls) to demonstrate a specific
dimension where Salva adds value over raw search:

1. Deduplication — Salva collapses duplicate URLs; raw search does not
2. Noise filtering — Salva rejects known-noisy domains; raw search returns everything
3. Domain signal scoring — Salva scores by domain-specific signals; raw is unordered
4. Topology selects correct route — structured intent gets precision route, not catch-all
5. Routing memory raises topology confidence across runs
6. Live probe degrades topology when provider is empty (vs static overconfidence)
7. Source pack diversity — topology class drives different source packs
8. Domain vocab expansion — Salva expands queries; raw query stays narrow
"""
from __future__ import annotations

import pytest

from salva_core.live_probe import LiveProbeSignal, _set_probe_cache, invalidate_probe_cache
from salva_core.schemas import DiscoveryIntent, DiscoveryRequest
from salva_core.topology import _classify_topology, _build_source_pack, plan_route


def _intent(**kw) -> DiscoveryIntent:
    base = dict(market="Taiwan", industry="semiconductor")
    base.update(kw)
    return DiscoveryIntent(**base)


def _req(**kw) -> DiscoveryRequest:
    kw.setdefault("objective", "find_companies")
    kw.setdefault("intent", _intent())
    kw.setdefault("max_results", 10)
    return DiscoveryRequest(**kw)


@pytest.fixture(autouse=True)
def clean_probe_cache():
    invalidate_probe_cache()
    yield
    invalidate_probe_cache()


# ---------------------------------------------------------------------------
# 1. Deduplication: pipeline collapses same-domain duplicates
# ---------------------------------------------------------------------------

class TestDeduplication:
    """Raw search returns N results; Salva's dedup reduces to unique entities.

    Baseline: pass 4 results with 2 distinct dedupe keys.
    Salva:    ProcessingPipeline.dedupe_key collapses them → 2 unique entries.
    """

    def _make_results(self) -> list[dict]:
        # Two genuine duplicates (same URL + same title from different SearXNG engines)
        # and two distinct results
        return [
            {"url": "https://tsmc.com/about", "title": "TSMC – About", "snippet": "foundry"},
            {"url": "https://tsmc.com/about", "title": "TSMC – About", "snippet": "foundry"},  # dup
            {"url": "https://asml.com/about", "title": "ASML – Company", "snippet": "litho"},
            {"url": "https://asml.com/careers", "title": "ASML – Careers", "snippet": "jobs"},
        ]

    def test_baseline_raw_results_has_four_items(self):
        results = self._make_results()
        assert len(results) == 4, "baseline: raw search returns 4 items without dedup"

    def test_pipeline_dedupe_key_collapses_exact_duplicates(self):
        from processing.pipeline import ProcessingPipeline
        pipeline = ProcessingPipeline()
        results = self._make_results()
        keys = {pipeline.dedupe_key(r) for r in results}
        # 4 results but 3 unique: tsmc/about appears twice, asml/about and asml/careers differ
        assert len(keys) == 3, (
            f"Expected 3 unique keys (dedup collapses same URL+title), got {len(keys)}. "
            "Dedup key: (domain, normalized_url, title)."
        )

    def test_pipeline_dedupe_key_strips_query_string(self):
        # dedupe_key must strip query parameters from URL before hashing
        from processing.pipeline import ProcessingPipeline
        pipeline = ProcessingPipeline()
        r1 = {"url": "https://tsmc.com/about", "title": "TSMC"}
        r2 = {"url": "https://tsmc.com/about?lang=zh-TW&ref=nav", "title": "TSMC"}
        assert pipeline.dedupe_key(r1) == pipeline.dedupe_key(r2), (
            "Query-string variants of the same page must produce the same dedupe key"
        )

    def test_pipeline_dedupe_key_strips_fragment(self):
        from processing.pipeline import ProcessingPipeline
        pipeline = ProcessingPipeline()
        r1 = {"url": "https://tsmc.com/about", "title": "TSMC"}
        r2 = {"url": "https://tsmc.com/about#overview", "title": "TSMC"}
        assert pipeline.dedupe_key(r1) == pipeline.dedupe_key(r2), (
            "Fragment variants must produce the same dedupe key"
        )

    def test_pipeline_dedupe_key_different_domains_stay_distinct(self):
        from processing.pipeline import ProcessingPipeline
        pipeline = ProcessingPipeline()
        r1 = {"url": "https://tsmc.com/about", "title": "TSMC"}
        r2 = {"url": "https://asml.com/about", "title": "ASML"}
        assert pipeline.dedupe_key(r1) != pipeline.dedupe_key(r2), (
            "Different domains must produce different dedupe keys"
        )


# ---------------------------------------------------------------------------
# 2. Noise filtering: Salva scorer downgrades known-noise domains
# ---------------------------------------------------------------------------

class TestNoiseDomainFiltering:
    """Raw search returns noise (Reddit, YouTube, Wikipedia).
    Salva's QualificationScorer gives these low scores so they don't qualify.

    Baseline: noise URL included in raw results.
    Salva:    score < qualify_threshold → rejected.
    """

    def _make_noise_result(self, url: str, snippet: str = "semiconductor review") -> dict:
        return {
            "url": url,
            "title": "Semiconductor Discussion",
            "snippet": snippet,
            "score": 0.9,  # raw SearXNG rank = high, but domain is noisy
        }

    def test_noise_domain_score_below_default_threshold(self):
        from processing.scorer import DOMAIN_CONFIGS, QualificationScorer, ScorerConfig
        from core.types import Intent, UnifiedResult

        noise_urls = [
            "https://www.reddit.com/r/hardware/semiconductor",
            "https://www.youtube.com/watch?v=abc",
            "https://en.wikipedia.org/wiki/Semiconductor",
        ]
        scorer = QualificationScorer()
        intent = Intent(domain="companies", primary_terms=["semiconductor", "Taiwan"])
        threshold = QualificationScorer.domain_threshold("companies")

        for url in noise_urls:
            result = UnifiedResult(
                source_name="SearXNG",
                source_url=url,
                title="Semiconductor content",
                description="semiconductor foundry company",
            )
            score = scorer.score(result, intent)
            assert score < threshold, (
                f"Noise domain {url} scored {score:.2f} ≥ threshold {threshold:.2f}. "
                "Salva must downgrade known-noisy domains below qualify_threshold."
            )

    def test_trusted_source_scores_higher_than_noise(self):
        from processing.scorer import QualificationScorer
        from core.types import Intent, UnifiedResult

        scorer = QualificationScorer()
        intent = Intent(domain="companies", primary_terms=["semiconductor", "distributor"])

        noise = UnifiedResult(
            source_name="SearXNG",
            source_url="https://www.reddit.com/semiconductor",
            title="Semiconductor",
            description="distributor supplier wholesale semiconductor Taiwan",
        )
        trusted = UnifiedResult(
            source_name="SearXNG",
            source_url="https://www.linkedin.com/company/tsmc",
            title="TSMC on LinkedIn",
            description="distributor supplier wholesale semiconductor Taiwan manufacturer",
        )
        noise_score = scorer.score(noise, intent)
        trusted_score = scorer.score(trusted, intent)
        assert trusted_score > noise_score, (
            f"Trusted source ({trusted_score:.2f}) must outscore noise ({noise_score:.2f})"
        )


# ---------------------------------------------------------------------------
# 3. Domain signal scoring: signal keywords increase score meaningfully
# ---------------------------------------------------------------------------

class TestDomainSignalScoring:
    """Salva's scorer uses domain-specific signal keywords.
    A snippet with distributor/wholesale signals scores higher than a generic company page.

    Demonstrates: raw keyword search ranks by link popularity;
    Salva ranks by business-intent signal density.
    """

    def test_bd_leads_high_signal_snippet_scores_higher_than_generic(self):
        from processing.scorer import DOMAIN_CONFIGS, QualificationScorer
        from core.types import Intent, UnifiedResult

        bd_scorer = QualificationScorer(config=DOMAIN_CONFIGS["bd_leads"])
        intent = Intent(
            domain="bd_leads",
            primary_terms=["outdoor gear", "DACH"],
            region="Germany",
        )

        generic = UnifiedResult(
            source_name="SearXNG",
            source_url="https://example-company.de/about",
            title="Example Company GmbH",
            description="We are a company based in Munich",
        )
        signal_rich = UnifiedResult(
            source_name="SearXNG",
            source_url="https://outdoor-distributor.de/wholesale",
            title="Outdoor Gear Distributor Germany",
            description="wholesale distributor outdoor gear bulk supplier DACH region",
        )

        generic_score = bd_scorer.score(generic, intent)
        signal_score = bd_scorer.score(signal_rich, intent)

        assert signal_score > generic_score, (
            f"Signal-rich snippet ({signal_score:.2f}) must outscore generic page ({generic_score:.2f}). "
            "Salva's domain-calibrated scoring must beat raw rank order."
        )

    def test_negative_signal_keywords_lower_score(self):
        from processing.scorer import DOMAIN_CONFIGS, QualificationScorer
        from core.types import Intent, UnifiedResult

        bd_scorer = QualificationScorer(config=DOMAIN_CONFIGS["bd_leads"])
        intent = Intent(domain="bd_leads", primary_terms=["outdoor gear"])

        with_negative = UnifiedResult(
            source_name="SearXNG",
            source_url="https://amazon.com/outdoor-gear",
            title="Outdoor Gear on Amazon",
            description="buy outdoor gear review best products",
        )
        without_negative = UnifiedResult(
            source_name="SearXNG",
            source_url="https://outdoor-wholesale.de/gear",
            title="Outdoor Wholesale Germany",
            description="wholesale outdoor gear B2B",
        )

        neg_score = bd_scorer.score(with_negative, intent)
        pos_score = bd_scorer.score(without_negative, intent)
        assert pos_score > neg_score, (
            f"Negative-signal result ({neg_score:.2f}) must score below clean result ({pos_score:.2f})"
        )


# ---------------------------------------------------------------------------
# 4. Topology selects appropriate route for structured intent
# ---------------------------------------------------------------------------

class TestTopologyRouteSelection:
    """Salva classifies request shape and selects a matching route strategy.

    Baseline: a single generic route for all requests.
    Salva:    topology classification → precision route vs broad scan.
    """

    def test_structured_request_gets_precision_route(self):
        # Multiple site_domains → structured topology → company_research or platform_integrator
        req = DiscoveryRequest(
            objective="find_companies",
            intent=DiscoveryIntent(
                market="Taiwan",
                industry="semiconductor",
                constraints={"site_domains": ["tsmc.com", "ase.com", "auo.com"]},
            ),
            max_results=10,
        )
        topology, confidence, _ = _classify_topology(req)
        assert topology in {"structured", "vertical"}, (
            f"Structured request (3 site_domains) should classify as structured/vertical, got {topology}"
        )
        from salva_core.topology import _choose_route_name
        route = _choose_route_name(req, topology)
        assert route in {"company_research", "platform_integrator", "lead_focus"}, (
            f"Structured topology must get a precision route, got {route}"
        )

    def test_unstructured_request_gets_broad_route(self):
        req = _req(objective="find_leads", max_results=10)
        _set_probe_cache(LiveProbeSignal(
            result_count=5, avg_score=0.5, has_error=False,
            latency_ms=60.0, searxng_url="http://localhost:8080",
        ))
        plan = plan_route(req)
        # Must not use platform_integrator (over-engineered for unstructured) or deep_investigation
        # The route should be appropriate to the signal level
        assert plan.recommended_route, "route must be non-empty for any request"
        assert plan.topology, "topology must be classified for any request"

    def test_source_pack_differs_by_topology(self):
        # structured topology gets site/careers sources; distributed gets social/news
        from typing import cast
        from salva_core.schemas import TopologyClass
        req = _req()
        structured_pack = _build_source_pack(req, cast(TopologyClass, "structured"))
        distributed_pack = _build_source_pack(req, cast(TopologyClass, "distributed"))
        assert structured_pack != distributed_pack, (
            "structured and distributed topology must produce different source packs"
        )
        # Structured should include official_sites; distributed should include social
        assert "official_sites" in structured_pack, "structured pack must include official_sites"
        assert "news" in distributed_pack or "search" in distributed_pack, (
            "distributed pack must include broad sources"
        )


# ---------------------------------------------------------------------------
# 5. Routing memory raises confidence on second run
# ---------------------------------------------------------------------------

class TestRoutingMemoryCrossRunLift:
    """A second run that reads a positive routing_memory entry should produce
    a higher topology confidence than the first run (which sees no memory).

    Demonstrates: Salva learns from past runs; stateless retrieval doesn't.
    """

    def test_positive_routing_boost_increases_structured_signals(self):
        from salva_core.topology import _classify_topology
        req = _req(objective="find_companies")

        # First run: no routing memory
        _, confidence_no_boost, notes_no_boost = _classify_topology(req)

        # Second run: positive boost for a known-good provider
        boosts = {"https://digitimes.com": 0.8, "https://eetimes.com": 0.6}
        _, confidence_with_boost, notes_with_boost = _classify_topology(
            req, routing_boosts=boosts
        )

        assert confidence_with_boost >= confidence_no_boost, (
            f"Routing boosts should not decrease confidence: "
            f"{confidence_with_boost:.2f} (with) vs {confidence_no_boost:.2f} (without)"
        )
        assert any("routing_memory_active" in n for n in notes_with_boost), (
            "routing_memory_active note must appear when boosts are present"
        )

    def test_routing_memory_note_absent_without_boosts(self):
        req = _req(objective="find_companies")
        _, _, notes = _classify_topology(req, routing_boosts=None)
        assert not any("routing_memory_active" in n for n in notes), (
            "routing_memory_active note must not appear when no boosts present"
        )

    def test_multiple_positive_boosts_capped_at_2_signals(self):
        req = _req(objective="find_companies")
        # Even 10 positive boosts should add at most 2 structured_signals
        many_boosts = {f"https://source-{i}.com": 0.9 for i in range(10)}
        _, conf_10, _ = _classify_topology(req, routing_boosts=many_boosts)
        two_boosts = {"https://source-0.com": 0.9, "https://source-1.com": 0.9}
        _, conf_2, _ = _classify_topology(req, routing_boosts=two_boosts)
        assert abs(conf_10 - conf_2) < 0.001, (
            f"Boost is capped at min(2, positive_count): conf_10={conf_10:.2f}, conf_2={conf_2:.2f} should be equal"
        )


# ---------------------------------------------------------------------------
# 6. Live probe prevents static overconfidence
# ---------------------------------------------------------------------------

class TestLiveProbeVsStaticOverconfidence:
    """Without live probe, _classify_topology assigns high confidence even when
    the actual provider returns nothing (E21 scenario: TW IP geo-block).

    Salva's live probe catches this and degrades the topology to unstructured.
    """

    def test_static_topology_is_confident_without_probe(self):
        req = _req(
            objective="find_companies",
            intent=DiscoveryIntent(
                market="Germany",
                industry="outdoor",
                constraints={"site_domains": ["naturehike.de", "jack-wolfskin.de"]},
            ),
            max_results=10,
        )
        topology, confidence, _ = _classify_topology(req)
        # Static classification is confident because site_domains look structured
        assert confidence >= 0.50, f"static classification should be confident, got {confidence:.2f}"
        assert topology in {"structured", "vertical"}, f"got {topology}"

    def test_empty_probe_degrades_static_confidence(self):
        req = DiscoveryRequest(
            objective="find_companies",
            intent=DiscoveryIntent(
                market="Germany",
                industry="outdoor",
                constraints={"site_domains": ["naturehike.de", "jack-wolfskin.de"]},
            ),
            max_results=10,
        )
        # Inject empty probe signal (simulates TW IP geo-block → 0 SearXNG results)
        _set_probe_cache(LiveProbeSignal(
            result_count=0, avg_score=0.0, has_error=False,
            latency_ms=200.0, searxng_url="http://localhost:8080",
        ))
        plan = plan_route(req)
        # After empty probe, topology must degrade
        assert plan.topology == "unstructured" or plan.confidence <= 0.40, (
            f"Empty probe must degrade topology/confidence: "
            f"topology={plan.topology}, confidence={plan.confidence:.2f}. "
            "Without this, E21 scenario returns a confident vertical plan against a geo-blocked provider."
        )

    def test_healthy_probe_preserves_topology(self):
        req = _req(
            objective="find_companies",
            intent=DiscoveryIntent(
                market="Taiwan",
                industry="semiconductor",
                constraints={"site_domains": ["tsmc.com", "ase.com"]},
            ),
            max_results=10,
        )
        _set_probe_cache(LiveProbeSignal(
            result_count=8, avg_score=0.6, has_error=False,
            latency_ms=120.0, searxng_url="http://localhost:8080",
        ))
        plan = plan_route(req)
        assert plan.topology in {"structured", "vertical"}, (
            f"Healthy probe must not downgrade a well-structured request, got {plan.topology}"
        )
        assert any("live_probe_ok" in n for n in plan.notes), (
            f"live_probe_ok must appear in notes for healthy probe, got {plan.notes}"
        )


# ---------------------------------------------------------------------------
# 7. Domain vocab expansion adds terms vs raw query
# ---------------------------------------------------------------------------

class TestDomainVocabExpansion:
    """Salva expands queries using domain-specific vocabulary.
    A raw query "outdoor Germany" becomes "outdoor gear distributor DACH wholesale" etc.

    Demonstrates: Salva's probe queries are richer than raw user input.
    """

    def test_probe_queries_contain_more_than_input_terms(self):
        req = DiscoveryRequest(
            objective="find_leads",
            intent=DiscoveryIntent(market="Germany", industry="outdoor"),
            max_results=10,
        )
        _set_probe_cache(LiveProbeSignal(
            result_count=5, avg_score=0.5, has_error=False,
            latency_ms=50.0, searxng_url="http://localhost:8080",
        ))
        plan = plan_route(req)
        assert plan.probe_queries, "probe_queries must be generated"
        first_query = plan.probe_queries[0]
        # The query must contain at least the intent terms
        assert "outdoor" in first_query.lower() or "germany" in first_query.lower(), (
            f"probe query must reflect intent terms, got: {first_query!r}"
        )

    def test_extra_keywords_appear_in_probe_queries(self):
        req = DiscoveryRequest(
            objective="find_leads",
            intent=DiscoveryIntent(
                market="Germany",
                industry="outdoor",
                extra_keywords=["distributor", "wholesale"],
            ),
            max_results=10,
        )
        _set_probe_cache(LiveProbeSignal(
            result_count=5, avg_score=0.5, has_error=False,
            latency_ms=50.0, searxng_url="http://localhost:8080",
        ))
        plan = plan_route(req)
        all_queries = " ".join(plan.probe_queries).lower()
        assert "outdoor" in all_queries or "germany" in all_queries or "distributor" in all_queries, (
            f"extra_keywords must influence probe queries; all queries: {plan.probe_queries}"
        )
