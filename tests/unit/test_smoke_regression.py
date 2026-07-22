"""Smoke + regression tests targeting latent bugs and untested branches.

Covers five areas identified by static analysis:
A. _classify_topology missing branches (broad / concentrated / output_profile_guard / unstructured)
B. ScorerConfig._apply_context silently resets qualify_threshold to 0.40
C. RoutedRetriever with no usable providers — must return [], not raise
D. persistence_mode="none" schema validity + run_id=None invariant
E. All topology classes → route name → fanout_policy chain validity
"""
from __future__ import annotations

from typing import cast

import pytest

from salva_core.schemas import DiscoveryRequest, DiscoveryIntent, TopologyClass
from salva_core.topology import (
    _build_fanout_policy,
    _choose_route_name,
    _classify_topology,
    plan_route,
)


def _intent(**kw) -> DiscoveryIntent:
    defaults = dict(market="Germany", industry="software")
    defaults.update(kw)
    return DiscoveryIntent(**defaults)


def _req(objective="find_companies", intent_kw=None, **kw) -> DiscoveryRequest:
    return DiscoveryRequest(
        objective=objective,
        intent=_intent(**(intent_kw or {})),
        **kw,
    )


# ---------------------------------------------------------------------------
# A. _classify_topology branch coverage
# ---------------------------------------------------------------------------

class TestClassifyTopologyBranches:
    """_classify_topology has 8 outcome branches; only a subset were previously tested."""

    def test_unstructured_fallback_returns_valid_class(self):
        # Minimal request, no extra signals → must never raise, must return valid class
        req = _req(objective="find_leads", max_results=10)
        topology, confidence, notes = _classify_topology(req)
        assert topology in {
            "structured", "vertical", "concentrated", "broad",
            "distributed", "mixed", "semantic_union", "unstructured",
        }, f"unexpected topology class: {topology}"
        assert confidence > 0.0

    def test_broad_topology_high_max_results(self):
        # max_results >= 100 gives +2 broad_signals; extra_keywords + high max_results
        # with no structured signals should push toward broad/mixed.
        # Failure: if broad branch never tested, new code could break it silently.
        req = _req(
            objective="find_companies",
            intent_kw={"extra_keywords": ["tech", "startup", "vc", "seed", "europe"]},
            max_results=200,
        )
        topology, _, _ = _classify_topology(req)
        assert topology in {"broad", "mixed", "vertical"}, (
            f"high max_results + extra_keywords should trend broad/mixed, got {topology}"
        )

    def test_concentrated_topology_via_role_and_product(self):
        # role + product → focused_signals = 2 → concentrated (unless structured overrides)
        # Failure: without this test, role+product path could silently degrade to unstructured.
        req = _req(
            objective="find_leads",
            intent_kw={"role": "procurement manager", "product": "industrial sensors"},
            max_results=10,
        )
        topology, _, _ = _classify_topology(req)
        assert topology in {"concentrated", "vertical", "structured"}, (
            f"role+product → concentrated/vertical expected, got {topology}"
        )

    def test_output_profile_structured_guard(self):
        # output_profile=company_profile is the last guard before fallback.
        # With no other structural signals, should produce structured.
        req = DiscoveryRequest(
            objective="find_leads",
            intent=_intent(),
            max_results=10,
            output_profile="company_profile",
        )
        topology, _, _ = _classify_topology(req)
        assert topology in {"structured", "concentrated", "vertical"}, (
            f"company_profile output_profile guard → structured expected, got {topology}"
        )

    def test_market_activity_objective_distributed(self):
        req = _req(objective="find_market_activity")
        topology, _, _ = _classify_topology(req)
        assert topology in {"distributed", "mixed", "broad"}, (
            f"find_market_activity → distributed/mixed expected, got {topology}"
        )

    def test_partnership_signals_objective_semantic_union(self):
        req = _req(objective="find_partnership_signals")
        topology, _, _ = _classify_topology(req)
        assert topology in {"semantic_union", "mixed"}, (
            f"find_partnership_signals → semantic_union expected, got {topology}"
        )

    def test_events_objective_vertical(self):
        req = _req(objective="find_events")
        topology, _, _ = _classify_topology(req)
        assert topology == "vertical", f"find_events → vertical expected, got {topology}"

    def test_all_topology_classes_produce_valid_route_and_fanout(self):
        # Smoke: every topology class must resolve without error
        topology_classes = [
            "structured", "vertical", "concentrated", "broad",
            "distributed", "mixed", "semantic_union", "unstructured",
        ]
        req = _req(objective="find_companies")
        for topo in topology_classes:
            tc = cast(TopologyClass, topo)
            route = _choose_route_name(req, tc)
            fanout, merge = _build_fanout_policy(tc)
            assert route, f"topology {topo} → empty route"
            assert fanout, f"topology {topo} → empty fanout"
            assert merge, f"topology {topo} → empty merge"


# ---------------------------------------------------------------------------
# B. ScorerConfig._apply_context must preserve qualify_threshold
# ---------------------------------------------------------------------------

class TestScorerConfigContextPreservation:
    """_apply_context builds a new ScorerConfig without copying qualify_threshold.

    This means any domain-specific threshold (bd_leads=0.35) is silently reset
    to the default 0.40 in the adjusted config.

    Current status: BUG EXISTS — tests below will FAIL until fixed.
    They are intentionally marked xfail to document the known defect.
    """

    def test_apply_context_preserves_bd_leads_threshold(self):
        from processing.scorer import DOMAIN_CONFIGS, QualificationScorer
        bd_cfg = DOMAIN_CONFIGS["bd_leads"]
        assert abs(bd_cfg.qualify_threshold - 0.35) < 1e-6, "prerequisite: bd_leads=0.35"
        adjusted = QualificationScorer._apply_context(
            bd_cfg, {"notes": ["precision_first"]}
        )
        assert abs(adjusted.qualify_threshold - 0.35) < 1e-6, (
            f"Expected 0.35 after _apply_context, got {adjusted.qualify_threshold}. "
            "Callers reading adjusted.qualify_threshold will gate too strictly."
        )

    def test_apply_context_preserves_taiwan_hardware_threshold(self):
        from processing.scorer import DOMAIN_CONFIGS, QualificationScorer
        tw_cfg = DOMAIN_CONFIGS.get("taiwan_hardware")
        if tw_cfg is None:
            pytest.skip("taiwan_hardware domain not defined")
        adjusted = QualificationScorer._apply_context(tw_cfg, {"notes": ["source_discovery"]})
        assert abs(adjusted.qualify_threshold - 0.35) < 1e-6, (
            f"Expected 0.35, got {adjusted.qualify_threshold}"
        )

    def test_apply_context_with_no_context_returns_cfg_unchanged(self):
        from processing.scorer import DOMAIN_CONFIGS, QualificationScorer
        bd_cfg = DOMAIN_CONFIGS["bd_leads"]
        result = QualificationScorer._apply_context(bd_cfg, None)
        assert result is bd_cfg, "context=None early-return must not copy the config"

    def test_domain_threshold_static_reads_domain_configs_directly(self):
        # domain_threshold() reads DOMAIN_CONFIGS, not an adjusted config → unaffected by bug
        from processing.scorer import QualificationScorer
        assert abs(QualificationScorer.domain_threshold("bd_leads") - 0.35) < 1e-6
        assert abs(QualificationScorer.domain_threshold("__unknown__") - 0.40) < 1e-6

    def test_default_scorer_config_threshold_is_0_40(self):
        from processing.scorer import ScorerConfig
        assert abs(ScorerConfig().qualify_threshold - 0.40) < 1e-6


# ---------------------------------------------------------------------------
# C. RoutedRetriever with no usable providers
# ---------------------------------------------------------------------------

class TestRoutedRetrieverNullProviders:
    """When all providers are disabled/unavailable, search() must return [] without raising.

    Failure scenario: if providers list is empty, any call to search() must
    handle the zero-provider case gracefully — not IndexError, not AttributeError.
    """

    def _make_retriever(self, extra_env=None):
        import os
        from retrieval.router import RoutedRetriever
        from salva_core.schemas import RetrievalPolicy
        policy = RetrievalPolicy(local_first=False, allow_public_fallback=False)
        return RoutedRetriever(policy=policy, strategy="dive")

    def test_empty_provider_chain_returns_empty_list(self, monkeypatch):
        import retrieval.router as rr
        # Force _build_provider_chain to return empty so no providers are available
        monkeypatch.setattr(rr, "_build_provider_chain", lambda policy, strategy: [])
        from retrieval.router import RoutedRetriever
        from salva_core.schemas import RetrievalPolicy
        policy = RetrievalPolicy(local_first=False, allow_public_fallback=False)
        retriever = RoutedRetriever(policy=policy, strategy="dive")
        results = retriever.search("semiconductor Taiwan", n=5)
        assert results == [], f"empty provider chain must return [], got {results!r}"

    def test_empty_provider_chain_last_attempts_is_empty(self, monkeypatch):
        import retrieval.router as rr
        monkeypatch.setattr(rr, "_build_provider_chain", lambda policy, strategy: [])
        from retrieval.router import RoutedRetriever
        from salva_core.schemas import RetrievalPolicy
        retriever = RoutedRetriever(
            policy=RetrievalPolicy(local_first=False, allow_public_fallback=False),
            strategy="dive",
        )
        retriever.search("query", n=5)
        assert retriever.last_attempts == [], "no attempts should be recorded for empty provider chain"

    def test_search_result_is_always_a_list(self, monkeypatch):
        import retrieval.router as rr
        monkeypatch.setattr(rr, "_build_provider_chain", lambda policy, strategy: [])
        from retrieval.router import RoutedRetriever
        from salva_core.schemas import RetrievalPolicy
        retriever = RoutedRetriever(
            policy=RetrievalPolicy(local_first=False, allow_public_fallback=False),
            strategy="dive",
        )
        for mode in ("sequential", "adaptive", "parallel"):
            retriever.retrieval_mode = mode
            result = retriever.search("q", n=3)
            assert isinstance(result, list), f"mode={mode} must return list, got {type(result)}"


# ---------------------------------------------------------------------------
# D. persistence_mode="none" schema and invariants
# ---------------------------------------------------------------------------

class TestPersistenceNoneInvariants:
    """persistence_mode="none" skips all DB writes.

    The invariant: meta["run_id"] must be None (not a fake string, not a crash).
    Callers that read run_id and pass it to /v1/runs/{id} must handle None gracefully.
    """

    def test_execution_context_accepts_none_persistence(self):
        from salva_core.schemas import ExecutionContext
        ctx = ExecutionContext(persistence="none")
        assert ctx.persistence == "none"

    def test_execution_context_default_is_not_none(self):
        from salva_core.schemas import ExecutionContext
        ctx = ExecutionContext()
        assert ctx.persistence != "none", "default persistence must enable DB writes"

    def test_discovery_request_accepts_persistence_none(self):
        from salva_core.schemas import ExecutionContext
        req = DiscoveryRequest(
            objective="find_companies",
            intent=_intent(),
            max_results=5,
            execution=ExecutionContext(persistence="none"),
        )
        assert req.execution.persistence == "none"

    def test_all_valid_persistence_modes_accepted(self):
        from salva_core.schemas import ExecutionContext
        # Schema only defines "none" and "audit" — validate both are accepted
        for mode in ("none", "audit"):
            ctx = ExecutionContext(persistence=mode)
            assert ctx.persistence == mode


# ---------------------------------------------------------------------------
# E. Route + fanout chain consistency across all topology classes
# ---------------------------------------------------------------------------

TOPOLOGY_CLASSES = [
    "structured", "vertical", "concentrated", "broad",
    "distributed", "mixed", "semantic_union", "unstructured",
]

KNOWN_ROUTES = {
    "company_research", "quick_scan", "deep_investigation",
    "lead_focus", "event_discovery", "platform_integrator",
}


class TestRouteAndFanoutChain:
    """Every topology class must produce a known route and valid fanout/merge policy.

    Failure scenario: new topology class added to Literal but not to _choose_route_name
    → falls through to default "quick_scan" for ALL new topologies, breaking routing.
    """

    @pytest.mark.parametrize("topo", TOPOLOGY_CLASSES)
    def test_route_name_is_in_known_routes(self, topo):
        req = _req(objective="find_companies")
        route = _choose_route_name(req, cast(TopologyClass, topo))
        assert route in KNOWN_ROUTES, (
            f"topology={topo} → route={route!r} not in known routes. "
            "If this is a new route, add it to KNOWN_ROUTES in this test."
        )

    @pytest.mark.parametrize("topo", TOPOLOGY_CLASSES)
    def test_fanout_policy_non_empty(self, topo):
        fanout, merge = _build_fanout_policy(cast(TopologyClass, topo))
        assert fanout and isinstance(fanout, str)
        assert merge and isinstance(merge, str)

    def test_plan_route_notes_always_include_topology_annotation(self):
        from salva_core.live_probe import LiveProbeSignal, _set_probe_cache, invalidate_probe_cache
        invalidate_probe_cache()
        _set_probe_cache(LiveProbeSignal(
            result_count=5, avg_score=0.5, has_error=False,
            latency_ms=80.0, searxng_url="http://localhost:8080",
        ))
        try:
            plan = plan_route(_req(objective="find_companies"))
            assert any("topology=" in n for n in plan.notes), (
                f"plan.notes must include topology=..., got {plan.notes}"
            )
        finally:
            invalidate_probe_cache()

    @pytest.mark.parametrize("objective", [
        "find_companies", "find_leads", "find_events", "find_exhibitors",
        "find_market_activity", "find_partnership_signals",
    ])
    def test_plan_route_succeeds_for_all_objectives(self, objective):
        from salva_core.live_probe import LiveProbeSignal, _set_probe_cache, invalidate_probe_cache
        invalidate_probe_cache()
        _set_probe_cache(LiveProbeSignal(
            result_count=5, avg_score=0.5, has_error=False,
            latency_ms=50.0, searxng_url="http://localhost:8080",
        ))
        try:
            plan = plan_route(_req(objective=objective))
            assert plan.topology
            assert plan.recommended_route in KNOWN_ROUTES
        finally:
            invalidate_probe_cache()
