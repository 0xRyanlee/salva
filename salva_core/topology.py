from __future__ import annotations

from typing import Any, cast

from salva_core.routes import resolve_route_entry
from salva_core.schemas import (
    DiscoveryRequest,
    TopologyClass,
    TopologyProbeErrorSurface,
    TopologyProbeRequest,
    TopologyProbeResponse,
    TopologyProbeResult,
    TopologyRoutePlan,
)

# Live probe is imported lazily inside _apply_live_probe to avoid pulling in
# retrieval/ at module import time (keeps unit tests fast).


def probe_topology(
    request: DiscoveryRequest,
    caller_preset: str | None = None,
    probe_budget: int = 4,
    routing_boosts: dict[str, float] | None = None,
) -> TopologyProbeResult:
    topology, confidence, notes = _classify_topology(
        request, caller_preset=caller_preset, routing_boosts=routing_boosts
    )
    probe_queries = _build_probe_queries(request, topology=topology, caller_preset=caller_preset, probe_budget=probe_budget)

    # L0-B: Adjust topology/confidence from live environment probe.
    # Skipped for caller_preset requests (preset implies caller already knows their topology).
    if probe_queries and not caller_preset:
        topology, confidence, notes = _apply_live_probe(
            topology, confidence, notes, probe_queries[0]
        )

    error_surface = _build_error_surface(request, topology=topology, probe_queries=probe_queries)
    return TopologyProbeResult(
        topology=topology,
        confidence=confidence,
        probe_queries=probe_queries,
        notes=notes,
        error_surface=error_surface,
    )


def plan_route(
    request: DiscoveryRequest,
    caller_preset: str | None = None,
    probe_budget: int = 4,
    probe: TopologyProbeResult | None = None,
    routing_boosts: dict[str, float] | None = None,
) -> TopologyRoutePlan:
    probe_result = probe or probe_topology(
        request, caller_preset=caller_preset, probe_budget=probe_budget,
        routing_boosts=routing_boosts,
    )
    route_name = _choose_route_name(request, probe_result.topology)
    route_entry = resolve_route_entry(route_name)
    source_pack = _build_source_pack(request, probe_result.topology)
    strategy_bias = _build_strategy_bias(request, probe_result.topology)
    fanout_policy, merge_policy = _build_fanout_policy(probe_result.topology)
    notes = [
        f"topology={probe_result.topology}",
        *probe_result.notes,
    ]
    if caller_preset:
        notes.insert(0, f"caller_preset={caller_preset}")
    return TopologyRoutePlan(
        topology=probe_result.topology,
        confidence=probe_result.confidence,
        recommended_route=route_name,
        recommended_objective=request.objective,
        source_pack=source_pack,
        strategy_bias=strategy_bias,
        fanout_policy=fanout_policy,
        merge_policy=merge_policy,
        probe_queries=list(probe_result.probe_queries),
        notes=notes,
        error_surface=_build_error_surface(request, topology=probe_result.topology, probe_queries=probe_result.probe_queries),
        route_entry=route_entry,
    )


def build_topology_probe_response(
    payload: TopologyProbeRequest,
) -> TopologyProbeResponse:
    probe = probe_topology(
        payload.discovery,
        caller_preset=payload.caller_preset,
        probe_budget=payload.probe_budget,
    )
    plan = plan_route(
        payload.discovery,
        caller_preset=payload.caller_preset,
        probe_budget=payload.probe_budget,
        probe=probe,
    )
    return TopologyProbeResponse(probe=probe, plan=plan)


def _classify_topology(
    request: DiscoveryRequest,
    caller_preset: str | None = None,
    routing_boosts: dict[str, float] | None = None,
) -> tuple[TopologyClass, float, list[str]]:
    objective = request.objective
    intent = request.intent
    constraints = intent.constraints
    site_domains = _collect_site_domains(constraints)
    hinted_sources = list(intent.domain_hints.source_hints) if intent.domain_hints else []
    signal_terms = list(intent.domain_hints.signal_terms) if intent.domain_hints else []

    structured_signals = len(site_domains) + len(hinted_sources)
    broad_signals = 0
    if request.max_results >= 100:
        broad_signals += 2
    if objective in {"find_market_activity", "find_partnership_signals"}:
        broad_signals += 2
    if len(intent.extra_keywords) >= 4:
        broad_signals += 1
    if len(signal_terms) >= 3:
        broad_signals += 1

    focused_signals = 0
    if intent.product:
        focused_signals += 1
    if intent.role:
        focused_signals += 1
    if len(intent.negative_keywords) >= 2:
        focused_signals += 1

    notes: list[str] = []
    if caller_preset:
        notes.append(f"caller_preset={caller_preset}")
    if site_domains:
        notes.append("site_domains_present")
    if hinted_sources:
        notes.append("source_hints_present")
    if broad_signals:
        notes.append("broadness_signals_present")

    # Routing memory: known-good sources from previous runs increase confidence
    # in focused search; each positive provider contributes up to +2 structured_signals.
    if routing_boosts:
        positive = sum(1 for b in routing_boosts.values() if b > 0.05)
        if positive:
            notes.append(f"routing_memory_active")
            structured_signals += min(2, positive)

    if structured_signals >= 3 and broad_signals >= 2:
        return cast(TopologyClass, "mixed"), _confidence(structured_signals + broad_signals), [*notes, "structured_and_broad_signals"]
    if structured_signals >= 2:
        return cast(TopologyClass, "structured"), _confidence(structured_signals), [*notes, "explicit_source_pack"]
    if objective == "find_market_activity":
        return cast(TopologyClass, "distributed"), _confidence(2 + broad_signals), [*notes, "market_activity_prefers_source_diversity"]
    if objective == "find_partnership_signals":
        return cast(TopologyClass, "semantic_union"), _confidence(2 + focused_signals), [*notes, "signals_should_be_compared_jointly"]
    if objective == "find_events":
        return cast(TopologyClass, "vertical"), _confidence(2 + focused_signals), [*notes, "event_vertical"]
    if objective == "find_exhibitors":
        return cast(TopologyClass, "vertical"), _confidence(2 + focused_signals), [*notes, "exhibitor_vertical"]
    if broad_signals >= 2:
        return cast(TopologyClass, "broad"), _confidence(broad_signals), [*notes, "wide_search_space"]
    if focused_signals >= 2:
        return cast(TopologyClass, "concentrated"), _confidence(focused_signals), [*notes, "role_or_product_focus"]
    if objective == "find_companies":
        return cast(TopologyClass, "vertical"), _confidence(2 + focused_signals), [*notes, "company_vertical"]
    if objective == "find_leads":
        return cast(TopologyClass, "concentrated"), _confidence(1 + focused_signals), [*notes, "lead_focus"]
    if request.output_profile in {"company_profile", "crm_contact"}:
        return cast(TopologyClass, "structured"), _confidence(2 + structured_signals), [*notes, "structured_output_surface"]
    return cast(TopologyClass, "unstructured"), 0.45, [*notes, "fallback_unstructured"]


def _build_probe_queries(
    request: DiscoveryRequest,
    topology: TopologyClass,
    caller_preset: str | None,
    probe_budget: int,
) -> list[str]:
    intent = request.intent
    root_terms = [term for term in [intent.market, intent.industry, intent.product, intent.role] if term]
    if intent.extra_keywords:
        root_terms.extend(intent.extra_keywords[:2])
    if not root_terms:
        root_terms.append(request.objective)

    probe_queries: list[str] = []
    probe_queries.append(" ".join(root_terms[:3]))
    if request.objective in {"find_market_activity", "find_partnership_signals"}:
        probe_queries.append(f'"{" ".join(root_terms[:2])}" signals')
    elif topology in {"structured", "mixed"}:
        source_hints = _collect_source_hints(intent)
        if source_hints:
            probe_queries.append(f'site:{source_hints[0]} "{" ".join(root_terms[:2])}"')
    elif topology in {"broad", "distributed"}:
        probe_queries.append(f'{" ".join(root_terms[:2])} news OR docs')
    elif topology in {"concentrated", "vertical"}:
        probe_queries.append(f'"{" ".join(root_terms[:2])}" "{" ".join(root_terms[2:3])}"'.strip())
    else:
        probe_queries.append(f'{" ".join(root_terms[:2])} overview')

    if caller_preset:
        probe_queries.append(f'{caller_preset} {" ".join(root_terms[:2])}'.strip())

    deduped: list[str] = []
    seen: set[str] = set()
    for query in probe_queries:
        normalized = " ".join(query.split())
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped[:probe_budget]


def _choose_route_name(request: DiscoveryRequest, topology: TopologyClass) -> str:
    if request.objective in {"find_events", "find_exhibitors"}:
        return "event_discovery"
    if request.objective in {"find_market_activity", "find_partnership_signals"}:
        return "deep_investigation"
    if topology in {"structured", "vertical"}:
        if request.output_profile in {"company_profile", "crm_contact"}:
            return "platform_integrator"
        if request.objective == "find_leads" or request.intent.role or request.intent.product:
            return "lead_focus"
        return "company_research"
    if topology in {"broad", "distributed", "mixed"}:
        return "deep_investigation"
    if topology == "semantic_union":
        return "deep_investigation"
    if topology == "concentrated":
        return "lead_focus" if request.objective == "find_leads" else "company_research"
    return "quick_scan"


def _build_source_pack(request: DiscoveryRequest, topology: TopologyClass) -> list[str]:
    intent = request.intent
    site_domains = _collect_site_domains(intent.constraints)
    hinted_sources = _collect_source_hints(intent)
    if topology == "structured":
        return [*site_domains, *hinted_sources, "official_sites", "careers_pages"]
    if topology == "vertical":
        return [*site_domains, *hinted_sources, "official_sites", "news"]
    if topology == "concentrated":
        return [*hinted_sources, *site_domains, "search", "company_pages"]
    if topology == "distributed":
        return [*hinted_sources, "search", "news", "social", "official_sites"]
    if topology == "semantic_union":
        return [*hinted_sources, "official_sites", "news", "community_discussion"]
    if topology == "mixed":
        return [*site_domains, *hinted_sources, "search", "official_sites", "news"]
    return [*site_domains, *hinted_sources, "search", "community_discussion"]


def _build_strategy_bias(request: DiscoveryRequest, topology: TopologyClass) -> list[str]:
    bias = ["dedupe_url_first"]
    if topology in {"structured", "vertical"}:
        bias.extend(["favor_precision", "prefer_source_schema"])
    elif topology in {"broad", "distributed"}:
        bias.extend(["favor_source_diversity", "allow_wider_fanout"])
    elif topology == "semantic_union":
        bias.extend(["preserve_multiple_evidence_trails", "compare_jointly"])
    elif topology == "mixed":
        bias.extend(["hybrid_precision_recall", "parallel_tools_ok"])
    else:
        bias.extend(["favor_short_queries", "fast_probe"])
    if request.intent.role or request.intent.product:
        bias.append("role_product_anchor")
    return bias


def _build_fanout_policy(topology: TopologyClass) -> tuple[str, str]:
    if topology in {"structured", "vertical", "concentrated"}:
        return "low_fanout", "strict_dedupe"
    if topology in {"broad", "distributed"}:
        return "parallel_fanout", "loose_union"
    if topology == "semantic_union":
        return "parallel_fanout", "joint_evidence_merge"
    if topology == "mixed":
        return "hybrid_fanout", "hybrid_merge"
    return "single_shot", "strict_dedupe"


def _build_error_surface(
    request: DiscoveryRequest,
    topology: TopologyClass,
    probe_queries: list[str],
) -> list[TopologyProbeErrorSurface]:
    route_name = _choose_route_name(request, topology)
    first_query = probe_queries[0] if probe_queries else None
    return [
        TopologyProbeErrorSurface(
            stage="probe",
            code="topology_misclassification",
            route=route_name,
            topology=topology,
            query=first_query,
            message="probe classified the target shape; inspect this if downstream results look off",
            actionable_hint="If the result set is too noisy or too narrow, re-check the topology and source pack before changing the objective.",
        ),
    ]


def _collect_site_domains(constraints: dict[str, Any]) -> list[str]:
    value = constraints.get("site_domains") or constraints.get("preferred_domains") or []
    if isinstance(value, str):
        return [value]
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _collect_source_hints(intent: Any) -> list[str]:
    if not intent.domain_hints:
        return []
    return [hint.strip() for hint in intent.domain_hints.source_hints if hint.strip()]


def _confidence(signal_count: int) -> float:
    return min(0.95, round(0.45 + 0.08 * signal_count, 2))


def _apply_live_probe(
    topology: TopologyClass,
    confidence: float,
    notes: list[str],
    probe_query: str,
) -> tuple[TopologyClass, float, list[str]]:
    """Adjust topology/confidence using a live SearXNG probe (cached per TTL).

    Degrades gracefully: any import error or disabled SearXNG returns inputs unchanged.
    On success, writes the observation back to routing_memory.
    """
    try:
        from salva_core.live_probe import get_or_run_probe
        signal = get_or_run_probe(probe_query, timeout=3.0)
    except Exception:
        return topology, confidence, notes

    if signal is None:
        return topology, confidence, notes

    if signal.has_error:
        return topology, confidence, [*notes, "live_probe_error"]

    # Write probe result back to routing_memory (authority_boost + latency).
    # Import the module (not the function) so monkeypatching in tests works correctly.
    try:
        import salva_core.persistence.hold as _hold
        _hold.record_probe_result(signal.searxng_url, signal.result_count, signal.latency_ms)
    except Exception:
        pass

    if signal.result_count == 0:
        # Provider returned nothing — hard degrade; static topology is unreliable.
        return (
            cast(TopologyClass, "unstructured"),
            0.35,
            [*notes, "live_probe_empty"],
        )

    if signal.result_count < 3:
        # Weak coverage — lower confidence but keep topology.
        return topology, round(confidence * 0.75, 2), [*notes, "live_probe_degraded"]

    return topology, confidence, [*notes, f"live_probe_ok(n={signal.result_count})"]
