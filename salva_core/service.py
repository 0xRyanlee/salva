from __future__ import annotations

from typing import Any

from core.controller import RoundSummary, SalvaController
from core.domain_vocab import DomainVocab, get_vocab
from core.types import Intent
from enrichment.plugins import enrich_entities
from processing.dedup import MemoryDeduplicator
from processing.extractor import BaseExtractor
from processing.scorer import QualificationScorer
from retrieval.policies import resolve_retrieval_policy
from retrieval.registry import available_provider_kinds
from retrieval.router import RoutedRetriever
from retrieval.source_metadata import classify_source_attempt
from salva_core.execution import execution_meta, resolve_execution_request
from salva_core.legacy import legacy_result_relations, legacy_result_to_entity
from salva_core.mode_resolver import resolve_experience_plan
from salva_core.navigation import build_mate_report, build_pilot_advice
from salva_core.persistence import get_db_path_for_project, persist_discovery_run, update_run_meta
from salva_core.persistence.hold import list_routing_memory, record_source_attempt as _record_source_attempt
from salva_core.routes import PROFILE_ROUTE_HINTS
from salva_core.schemas import (
    CanonicalEntity,
    CanonicalRelation,
    DiscoveryRequest,
    PilotRequest,
    RetrievalPolicy,
    RetrievalProviderConfig,
    SourceAttemptRecord,
    TelemetryRecord,
)
from salva_core.topology import plan_route

# ---------------------------------------------------------------------------
# Objective → domain mapping
# Unmapped objectives fall back to "general", not "bd_leads".
# "general" uses pure primary_terms with no industry-specific vocabulary.
# ---------------------------------------------------------------------------
OBJECTIVE_TO_DOMAIN: dict[str, str] = {
    "find_events":              "events",
    "find_exhibitors":          "events",
    "find_leads":               "bd_leads",
    "find_companies":           "companies",
    "find_market_activity":     "market_intel",
    "find_partnership_signals": "partnerships",
}


def _resolve_vocab(payload: DiscoveryRequest, domain: str) -> DomainVocab:
    """
    Build the final DomainVocab for this request:
        registry vocab for the resolved domain
        + caller-supplied domain_hints (merged on top, if present)
    """
    base = get_vocab(domain)
    hints = payload.intent.domain_hints
    if hints is None:
        return base
    caller_vocab = DomainVocab(
        synonym_groups  = hints.synonym_groups,
        region_variants = hints.region_variants,
        signal_terms    = hints.signal_terms,
        source_hints    = hints.source_hints,
        noise_terms     = hints.noise_terms,
    )
    return base.merge(caller_vocab)


def discovery_request_to_legacy_intent(payload: DiscoveryRequest) -> Intent:
    primary_terms: list[str] = []
    if payload.intent.product:
        primary_terms.append(payload.intent.product)
    # role is NOT added to primary_terms — it goes into Intent.roles and becomes a
    # role-type node in the keyword graph, keeping product as the lead primary term.
    primary_terms.extend(payload.intent.extra_keywords)
    if not primary_terms:
        primary_terms.append(payload.intent.industry)

    roles = [payload.intent.role] if payload.intent.role else []

    constraints = dict(payload.intent.constraints)
    constraints["objective"] = payload.objective
    constraints["output_profile"] = payload.output_profile

    domain = OBJECTIVE_TO_DOMAIN.get(payload.objective, "general")

    return Intent(
        domain=domain,
        primary_terms=primary_terms,
        region=payload.intent.market,
        roles=roles,
        negative_terms=payload.intent.negative_keywords,
        constraints=constraints,
        max_rounds=constraints.get("max_rounds", 3),
        results_per_round=min(payload.max_results, constraints.get("results_per_round", 30)),
    )


def run_discovery(payload: DiscoveryRequest) -> tuple[list[CanonicalEntity], list[CanonicalRelation], list[TelemetryRecord], dict[str, Any]]:
    payload = resolve_execution_request(payload)
    entities, relations, telemetry, meta, source_attempts = execute_discovery(payload)
    if payload.execution.persistence == "none":
        meta["run_id"] = None
        meta["feedback"] = {}
        return entities, relations, telemetry, meta

    db_path = get_db_path_for_project(payload.execution.project_id)
    run_id = persist_discovery_run(payload, entities, relations, telemetry, meta, source_attempts=source_attempts, path=db_path)
    feedback = build_request_feedback(run_id, payload, path=db_path)
    meta["run_id"] = run_id
    meta["feedback"] = feedback
    update_run_meta(run_id, {"feedback": feedback}, path=db_path)
    for attempt in source_attempts:
        if attempt.base_url:
            _record_source_attempt(attempt.base_url, attempt.succeeded, path=db_path)
    return entities, relations, telemetry, meta


def execute_discovery(
    payload: DiscoveryRequest,
) -> tuple[list[CanonicalEntity], list[CanonicalRelation], list[TelemetryRecord], dict[str, Any], list[SourceAttemptRecord]]:
    routing_boosts: dict[str, float] | None = None
    if payload.execution.persistence != "none":
        _db = get_db_path_for_project(payload.execution.project_id)
        _mem = list_routing_memory(top_k=50, path=_db)
        if _mem:
            routing_boosts = {r["source_url"]: r["authority_boost"] for r in _mem if r["authority_boost"] != 0.0}
    topology_plan = plan_route(payload, probe_budget=4, routing_boosts=routing_boosts or None)
    experience_plan = resolve_experience_plan(payload, topology_plan=topology_plan)
    intent = discovery_request_to_legacy_intent(payload)
    vocab = _resolve_vocab(payload, intent.domain)

    retrieval_policy = _build_profile_policy(
        payload, experience_plan.profile,
        site_domains=_extract_site_domains(payload.intent.constraints),
    )
    retrieval_mode = "sequential"
    retrievers = {
        "dive":   RoutedRetriever(policy=retrieval_policy, strategy="dive", retrieval_mode=retrieval_mode),
        "anchor": RoutedRetriever(policy=retrieval_policy, strategy="anchor", retrieval_mode=retrieval_mode),
        "radar":  RoutedRetriever(policy=retrieval_policy, strategy="radar", retrieval_mode=retrieval_mode),
        "pirate": RoutedRetriever(policy=retrieval_policy, strategy="pirate", retrieval_mode=retrieval_mode),
    }
    extractor    = BaseExtractor()
    from processing.dedup import BM25_DOMAIN_THRESHOLDS
    deduplicator = MemoryDeduplicator(
        fuzzy_title=True,
        bm25_threshold=BM25_DOMAIN_THRESHOLDS.get(intent.domain, 0.85),
    )
    scorer = _build_scorer(payload, intent.domain)

    from core.keyword_graph import KeywordGraph
    graph = KeywordGraph(intent=intent, vocab=vocab)

    # A3: seed from cross-run memory before first search round
    memory_seeds = _seed_graph_from_memory(graph, intent.domain, payload)

    scoring_context = _build_stability_scoring_context(payload, intent.domain)

    controller = SalvaController(
        intent=intent,
        retrievers=retrievers,
        extractor=extractor,
        deduplicator=deduplicator,
        scorer=scorer,
        qualify_threshold=_resolve_qualify_threshold(payload, intent.domain),
        results_per_query=min(10, max(1, payload.max_results)),
        keyword_graph=graph,
        experience_profile=experience_plan.profile,
        scoring_context=scoring_context,
    )
    results, summary = controller.run()

    entities = [legacy_result_to_entity(result, market=payload.intent.market) for result in results]
    entities, plugin_reports = enrich_entities(entities, payload)
    relations     = _collect_relations(results)
    telemetry     = _collect_telemetry(summary)
    source_attempts = _collect_source_attempts(retrievers)
    provider_kinds = _collect_provider_kinds(retrievers)

    meta = {
        "qualified_count":        summary.total_qualified,
        "raw_count":              summary.total_raw,
        "rounds":                 len(summary.rounds),
        "elapsed_seconds":        summary.elapsed_seconds,
        "retrieval_mode":         retrieval_policy.mode,
        "local_first":            retrieval_policy.local_first,
        "html_fallback":          retrieval_policy.html_fallback,
        "source_attempt_count":   len(source_attempts),
        "plugin_report_count":    len(plugin_reports),
        "plugin_reports":         [r.model_dump(mode="json") for r in plugin_reports],
        "enrichment_mode":        payload.enrichment.mode,
        "provider_count":         len(provider_kinds),
        "provider_kinds":         provider_kinds,
        "experience_profile":     experience_plan.profile,
        "experience_ux":          experience_plan.primary_ux,
        "experience_notes":       experience_plan.notes,
        "experience_mode_switches": experience_plan.mode_switches,
        "topology":               topology_plan.topology,
        "topology_confidence":    topology_plan.confidence,
        "retrieval_health":       topology_plan.retrieval_health,
        "recommended_route":      topology_plan.recommended_route,
        "source_pack":            topology_plan.source_pack,
        "strategy_bias":          topology_plan.strategy_bias,
        "fanout_policy":          topology_plan.fanout_policy,
        "merge_policy":           topology_plan.merge_policy,
        "probe_queries":          topology_plan.probe_queries,
        "domain":                 intent.domain,
        "domain_hints_active":    payload.intent.domain_hints is not None,
        "memory_seeds_used":      memory_seeds,
        "execution":              execution_meta(payload),
    }
    if payload.tenant_id is not None:
        meta["tenant_id"] = payload.tenant_id
    return entities, relations, telemetry, meta, source_attempts


def _resolve_qualify_threshold(payload: DiscoveryRequest, domain: str) -> float:
    """None (not explicitly set by the caller) -> domain-calibrated default.
    An explicit float -- including one that happens to equal 0.4 -- always wins.
    """
    if payload.qualify_threshold is not None:
        return payload.qualify_threshold
    return QualificationScorer.domain_threshold(domain)


def _build_scorer(payload: DiscoveryRequest, domain: str) -> QualificationScorer:
    """Apply vocabulary hints without allowing callers to self-declare source trust."""
    hints = payload.intent.domain_hints
    if not hints or not (hints.signal_terms or hints.noise_terms):
        return QualificationScorer()

    from processing.scorer import DOMAIN_CONFIGS, ScorerConfig

    base = DOMAIN_CONFIGS.get(domain, ScorerConfig())
    return QualificationScorer(ScorerConfig(
        high_signals=list(hints.signal_terms) or base.high_signals,
        med_signals=base.med_signals,
        negative_signals=list(hints.noise_terms) or base.negative_signals,
        noise_domains=base.noise_domains,
        trusted_sources=base.trusted_sources,
        w_content=base.w_content,
        w_contact=base.w_contact,
        w_signal=base.w_signal,
        w_region=base.w_region,
        w_source=base.w_source,
        w_recency=base.w_recency,
    ))


def _build_stability_scoring_context(payload: DiscoveryRequest, domain: str) -> dict[str, Any]:
    """Opt-in stability gating: {} unless payload.stability.enabled is True.

    payload.stability doesn't exist on DiscoveryRequest yet -- getattr()
    returns None until a follow-up card adds that field and exposes it via
    MCP/REST, at which point this starts actually running. Until then this
    function always returns {}, matching every other caller's existing
    behavior exactly (empty scoring_context merges into telemetry.metadata
    as a no-op).

    Computed once per discover() call here, not per round/candidate --
    compute_stability_signals() does one domain-level DB read.
    """
    stability_policy = getattr(payload, "stability", None)
    if stability_policy is None or not getattr(stability_policy, "enabled", False):
        return {}

    from salva_core.stability import compute_stability_signals

    db_path = get_db_path_for_project(payload.execution.project_id)
    signals = compute_stability_signals(
        domain, min_history=stability_policy.min_history, path=db_path
    )
    if signals is None:
        return {}

    stability_score = max(0.0, 1.0 - min(1.0, signals["drift"] + signals["volatility"]))
    return {
        "w_stability": stability_policy.penalty_strength,
        "stability_score": stability_score,
    }


def _seed_graph_from_memory(
    graph: Any,
    domain: str,
    payload: DiscoveryRequest,
    top_k: int = 5,
    path: str | None = None,
) -> int:
    """
    Wire A3: build a memory_reader closure and call graph.seed_from_memory().
    Returns the number of nodes injected (0 if no memory or error).
    """
    from salva_core.persistence import DEFAULT_DB_PATH, read_top_query_families_for_seeding
    memory_policy = payload.execution.memory
    if memory_policy.read_scope == "none":
        return 0

    db_path = path or DEFAULT_DB_PATH
    campaign_id: str | None = None
    memory_status: str | None = None
    if memory_policy.read_scope == "campaign_promoted":
        campaign_id = payload.execution.campaign_id
        memory_status = "promoted"
    elif memory_policy.read_scope == "campaign_all":
        campaign_id = payload.execution.campaign_id
    elif memory_policy.read_scope == "global_legacy":
        memory_status = "legacy"

    def memory_reader(d: str, k: int) -> list[dict[str, Any]]:
        return read_top_query_families_for_seeding(
            domain=d,
            objective=payload.objective,
            campaign_id=campaign_id,
            memory_status=memory_status,
            top_k=k,
            min_success_score=memory_policy.min_success_score,
            path=db_path,
        )

    return graph.seed_from_memory(memory_reader=memory_reader, top_k=top_k)


def build_request_feedback(
    run_id: str,
    payload: DiscoveryRequest,
    path: str | None = None,
) -> dict[str, Any]:
    mate = build_mate_report(run_id, path=path)
    pilot = build_pilot_advice(
        PilotRequest(run_id=run_id, discovery=payload, max_suggestions=5),
        path=path,
    )
    return {
        "mate":  mate.model_dump(mode="json",  exclude_none=True),
        "pilot": pilot.model_dump(mode="json", exclude_none=True),
    }


def _collect_relations(results: list[Any]) -> list[CanonicalRelation]:
    relation_map: dict[str, CanonicalRelation] = {}
    for result in results:
        for relation in legacy_result_relations(result):
            relation_map[relation.relation_id] = relation
    return list(relation_map.values())


def _collect_telemetry(summary: Any) -> list[TelemetryRecord]:
    records: list[TelemetryRecord] = []
    for round_summary in summary.rounds:
        records.extend(_round_telemetry(round_summary))
    return records


def _round_telemetry(round_summary: RoundSummary) -> list[TelemetryRecord]:
    records: list[TelemetryRecord] = []
    for item in round_summary.telemetry:
        records.append(TelemetryRecord(
            query=item.query,
            round_num=item.round_num,
            strategy=item.strategy,
            results_total=item.results_total,
            results_qualified=item.results_qualified,
            avg_score=item.avg_score,
            reject_reasons=item.reject_reasons,
            noise_domains=item.noise_domains,
            metadata={
                "round_strategy":  round_summary.strategy,
                "content_weights": round_summary.content_weights,
                "source_hints":    round_summary.source_hints,
                "notes":           round_summary.notes,
                **item.metadata,
            },
        ))
    return records


def _collect_source_attempts(retrievers: dict[str, Any]) -> list[SourceAttemptRecord]:
    attempts: list[SourceAttemptRecord] = []
    for strategy, retriever in retrievers.items():
        attempts.extend(
            _build_source_attempt_record(strategy, item)
            for item in retriever.last_attempts
        )
    return attempts


def _collect_provider_kinds(retrievers: dict[str, Any]) -> list[str]:
    kinds: list[str] = []
    seen: set[str] = set()
    for retriever in retrievers.values():
        for provider in getattr(retriever, "providers", []):
            kind = type(provider).__name__
            if kind not in seen:
                seen.add(kind)
                kinds.append(kind)
    return kinds


def _build_source_attempt_record(strategy: str, item: Any) -> SourceAttemptRecord:
    metadata = classify_source_attempt(item.base_url, item.succeeded, item.error)
    return SourceAttemptRecord(
        run_id="pending",
        strategy=strategy,
        base_url=item.base_url,
        mode=item.mode,
        source_class=metadata["source_class"],
        trust_level=metadata["trust_level"],
        risk_level=metadata["risk_level"],
        recommended_crawl_mode=metadata["recommended_crawl_mode"],
        result_count=item.result_count,
        succeeded=item.succeeded,
        error=item.error,
        format_used=item.format_used,
    )


def _build_profile_policy(
    payload: DiscoveryRequest,
    profile: str,
    site_domains: list[str] | None = None,
) -> RetrievalPolicy:
    """
    Build a RetrievalPolicy shaped by the resolved experience profile.

    Priority:
      1. Caller-explicit payload.retrieval.providers  → used as-is (no override)
      2. Profile-derived provider_kinds from PROFILE_ROUTE_HINTS → filtered by availability
      3. Registry default chain (no providers specified)

    Stealth and proxy fields are merged from profile hints onto the base policy.
    """
    base = resolve_retrieval_policy(payload.retrieval)
    updates: dict[str, Any] = {}

    if site_domains:
        updates["site_domains"] = site_domains

    # If the caller already specified providers, respect them entirely.
    if payload.retrieval.providers:
        return base.model_copy(update=updates) if updates else base

    hints = PROFILE_ROUTE_HINTS.get(profile, {})
    provider_kinds: list[str] = list(hints.get("provider_kinds", []))  # type: ignore[arg-type]

    if provider_kinds:
        available = available_provider_kinds()
        configs = [
            RetrievalProviderConfig(kind=kind)  # type: ignore[arg-type]
            for kind in provider_kinds
            if kind in available
        ]
        if configs:
            updates["providers"] = configs

    # Apply stealth from profile hints (can be overridden by env or policy field).
    if hints.get("obscura_stealth") and not base.obscura_stealth:
        updates["obscura_stealth"] = True

    return base.model_copy(update=updates) if updates else base


def _extract_site_domains(constraints: dict[str, Any]) -> list[str]:
    raw_values: list[str] = []
    for key in ("preferred_domains", "site_domains", "domains"):
        value = constraints.get(key)
        if isinstance(value, str):
            raw_values.extend(part.strip() for part in value.split(","))
        elif isinstance(value, list):
            raw_values.extend(str(item).strip() for item in value)

    cleaned: list[str] = []
    seen: set[str] = set()
    for value in raw_values:
        normalized = value.strip().lower().removeprefix("www.")
        if normalized and normalized not in seen:
            seen.add(normalized)
            cleaned.append(normalized)
    return cleaned
