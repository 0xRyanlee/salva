from __future__ import annotations

from datetime import UTC, datetime
from time import perf_counter
from typing import Any, Literal

from salva_core.evaluation import build_audit_report
from salva_core.mode_resolver import resolve_experience_plan
from salva_core.persistence import get_run, search_query_family_memory
from salva_core.planner import build_planner_response
from salva_core.pricing import resolve_pricing_quote
from salva_core.schemas import (
    DiscoveryRequest,
    MatePricing,
    MateReport,
    MateRequest,
    PilotAdvice,
    PilotRequest,
    PlannerRequest,
)


def build_mate_report(run_id: str, payload: MateRequest | None = None, path: str | None = None) -> MateReport:
    started_at = perf_counter()
    detail = get_run(run_id, path=path) if path is not None else get_run(run_id)
    if detail is None:
        raise KeyError(f"run not found: {run_id}")

    audit = build_audit_report(run_id, path=path)
    pricing = (payload.pricing if payload else MatePricing())
    pricing_quote = _resolve_pricing_quote(pricing)

    raw_count = int(audit.metrics.get("raw_count", 0) or 0)
    qualified_count = int(audit.metrics.get("qualified_count", 0) or 0)
    source_attempt_count = int(audit.source_attempt_count or 0)
    plugin_report_count = int(audit.plugin_report_count or 0)

    estimated_candidate_units_saved = max(raw_count - qualified_count, 0)
    estimated_time_saved_seconds = (
        estimated_candidate_units_saved * pricing.manual_review_seconds_per_candidate
        + max(source_attempt_count - 1, 0) * pricing.manual_retry_seconds_per_failed_source_attempt
    )
    estimated_llm_calls_saved = float(estimated_candidate_units_saved)
    estimated_tokens_saved = int(round(estimated_llm_calls_saved * pricing.tokens_per_candidate))

    estimated_api_cost_saved: float | None = None
    pricing_applied = pricing.usd_per_1k_tokens is not None or (
        pricing_quote is not None and pricing_quote.usd_per_1k_tokens is not None
    )
    resolved_usd_per_1k_tokens = pricing.usd_per_1k_tokens
    if resolved_usd_per_1k_tokens is None and pricing_quote is not None:
        resolved_usd_per_1k_tokens = pricing_quote.usd_per_1k_tokens

    if pricing_applied and resolved_usd_per_1k_tokens is not None:
        estimated_api_cost_saved = round(
            (estimated_tokens_saved / 1000.0) * float(resolved_usd_per_1k_tokens),
            4,
        )

    assumptions = [
        f"假設每個被過濾的候選項可避免 {pricing.manual_review_seconds_per_candidate:.1f} 秒的人工作業。",
        f"假設每個候選項會觸發約 {pricing.tokens_per_candidate} tokens 的後續 LLM / enrichment 成本。",
        f"假設每次失敗來源重試平均可省下 {pricing.manual_retry_seconds_per_failed_source_attempt:.1f} 秒。",
    ]
    if pricing_applied and resolved_usd_per_1k_tokens is not None:
        assumptions.append(f"使用 blended token 價格 `{resolved_usd_per_1k_tokens}` / 1K tokens 估算成本節省。")
    else:
        assumptions.append("未提供 token 價格時，只回傳節省 token 與時間，不估算美元成本。")

    notes: list[str] = []
    if qualified_count == 0 and raw_count > 0:
        notes.append("no_qualified_candidates")
    if plugin_report_count == 0 and audit.metrics.get("qualified_rate", 0.0) > 0:
        notes.append("no_plugin_activity")
    if audit.metrics.get("noise_rate", 0.0) > 0.5:
        notes.append("high_noise_rate")

    generation_latency_ms = round((perf_counter() - started_at) * 1000.0, 2)

    confidence = 0.78 if pricing_applied else 0.72
    if raw_count == 0:
        confidence = 0.45

    return MateReport(
        run_id=run_id,
        objective=detail["objective"],
        output_profile=detail["output_profile"],
        experience_profile=detail["meta"].get("experience_profile") or "quick_scan",
        generated_at=datetime.now(UTC),
        generation_latency_ms=generation_latency_ms,
        raw_count=raw_count,
        qualified_count=qualified_count,
        source_attempt_count=source_attempt_count,
        plugin_report_count=plugin_report_count,
        estimated_candidate_units_saved=estimated_candidate_units_saved,
        estimated_time_saved_seconds=round(estimated_time_saved_seconds, 2),
        estimated_llm_calls_saved=round(estimated_llm_calls_saved, 2),
        estimated_tokens_saved=estimated_tokens_saved,
        estimated_api_cost_saved=estimated_api_cost_saved,
        pricing_applied=pricing_applied,
        pricing_source_name=pricing_quote.source_name if pricing_quote else None,
        pricing_source_url=pricing_quote.source_url if pricing_quote else None,
        pricing_source_latency_ms=pricing_quote.source_latency_ms if pricing_quote else None,
        assumptions=assumptions,
        notes=notes,
        confidence=confidence,
        details={
            "audit_metrics": audit.metrics,
            "provider_kinds": audit.provider_kinds,
            "round_profiles": audit.round_profiles,
            "source_classes": audit.source_classes,
        },
    )


def build_pilot_advice(payload: PilotRequest, path: str | None = None) -> PilotAdvice:
    started_at = perf_counter()
    _detail, discovery = _resolve_discovery_context(payload, path=path)
    discovery = _apply_pilot_overrides(discovery, payload)
    planner_response = build_planner_response(
        PlannerRequest(
            discovery=discovery,
            caller_preset=payload.mode,
            question_budget=payload.max_suggestions,
            allow_llm_preprompt=False,
        )
    )
    topology_plan = planner_response.route_plan
    experience_plan = resolve_experience_plan(discovery, topology_plan=topology_plan)
    preprompt = planner_response.preprompt
    research_plan = planner_response.plan
    audit = build_audit_report(payload.run_id, path=path) if payload.run_id else None

    source: Literal["run", "request"] = "run" if payload.run_id else "request"
    qualified_rate = audit.metrics.get("qualified_rate", 0.0) if audit else 0.0
    noise_rate = audit.metrics.get("noise_rate", 0.0) if audit else 0.0
    source_success_rate = audit.metrics.get("source_success_rate", 0.0) if audit else 0.0
    plugin_report_count = audit.plugin_report_count if audit else 0

    preferred_domains = _extract_domains(discovery.intent.constraints)
    negative_terms = list(dict.fromkeys(discovery.intent.negative_keywords))
    next_queries = _build_next_queries(discovery, preferred_domains, payload.max_suggestions)
    semantic_matches = _build_semantic_matches(discovery, payload.max_suggestions, path=path)
    next_steps: list[str] = []
    mode_switches: list[str] = []
    notes: list[str] = []

    recommended_retrieval_mode = experience_plan.retrieval_mode
    recommended_enrichment_mode = experience_plan.enrichment_mode
    recommended_experience_profile = experience_plan.profile
    recommended_output_profile = experience_plan.output_profile
    round_budget = research_plan.round_budget
    clarification_mode = preprompt.clarification_mode
    needs_clarification = preprompt.clarification_needed
    clarifying_questions = preprompt.clarifying_questions
    replan_triggers = research_plan.replan_triggers
    stop_conditions = research_plan.stop_conditions

    if audit:
        if source_success_rate < 0.5:
            recommended_retrieval_mode = "wall_guarded"
            next_steps.append("先切到 wall_guarded，讓多 provider fallback 先保底。")
            mode_switches.append("retrieval.mode -> wall_guarded")
            notes.append("weak_source_reliability")
        elif noise_rate > 0.35:
            recommended_retrieval_mode = "cautious"
            next_steps.append("先收斂到 cautious，並加上更明確的站點與排除詞。")
            mode_switches.append("retrieval.mode -> cautious")
            notes.append("high_noise_rate")
        elif qualified_rate < 0.1:
            recommended_retrieval_mode = "resilient"
            next_steps.append("先維持 resilient，但收斂 query，改用 dive / anchor 先打準。")
            mode_switches.append("query.strategy -> dive/anchor")
            notes.append("low_qualified_rate")

        if plugin_report_count == 0 and audit.metrics.get("qualified_rate", 0.0) > 0:
            recommended_enrichment_mode = "selected"
            next_steps.append("若要深挖，先只開 omxl / site_html，避免全量 enrich 擴噪。")
            mode_switches.append("enrichment.mode -> selected")
            notes.append("no_plugin_activity")

        if audit.objective == "find_events":
            recommended_experience_profile = "event_discovery"
        elif audit.objective == "find_companies":
            recommended_experience_profile = "company_research"
        elif audit.objective in {"find_partnership_signals", "find_market_activity"}:
            recommended_experience_profile = "platform_integrator"
        else:
            recommended_experience_profile = experience_plan.profile

    if not next_steps:
        next_steps.extend(
            [
                "先以目前 profile 跑一輪，再用 audit / mate / benchmark 看哪個方向收斂最快。",
                "若第一輪命中太寬，先加 negative terms，再切到 anchor。",
            ]
        )

    if needs_clarification:
        next_steps.insert(0, "先讓 agent 問 1-3 個澄清問題，再進入執行。")
        if clarification_mode == "rule":
            clarification_mode = "agent"

    guidance_summary = _build_guidance_summary(
        discovery=discovery,
        experience_profile=recommended_experience_profile,
        topology=topology_plan.topology,
        recommended_route=topology_plan.recommended_route,
        round_budget=round_budget,
        clarification_mode=clarification_mode,
        needs_clarification=needs_clarification,
        retrieval_mode=recommended_retrieval_mode,
        enrichment_mode=recommended_enrichment_mode,
        source_success_rate=source_success_rate,
        noise_rate=noise_rate,
        qualified_rate=qualified_rate,
    )

    human_prompt = _build_human_prompt(
        discovery=discovery,
        experience_profile=recommended_experience_profile,
        topology=topology_plan.topology,
        recommended_route=topology_plan.recommended_route,
        round_budget=round_budget,
        clarification_mode=clarification_mode,
        needs_clarification=needs_clarification,
        clarifying_questions=clarifying_questions,
        replan_triggers=replan_triggers,
        stop_conditions=stop_conditions,
        next_steps=next_steps,
        next_queries=next_queries,
        preferred_domains=preferred_domains,
        negative_terms=negative_terms,
        retrieval_mode=recommended_retrieval_mode,
        enrichment_mode=recommended_enrichment_mode,
    )
    agent_prompt = _build_agent_prompt(
        discovery=discovery,
        experience_profile=recommended_experience_profile,
        topology=topology_plan.topology,
        recommended_route=topology_plan.recommended_route,
        round_budget=round_budget,
        clarification_mode=clarification_mode,
        needs_clarification=needs_clarification,
        clarifying_questions=clarifying_questions,
        replan_triggers=replan_triggers,
        stop_conditions=stop_conditions,
        next_steps=next_steps,
        next_queries=next_queries,
        preferred_domains=preferred_domains,
        negative_terms=negative_terms,
        retrieval_mode=recommended_retrieval_mode,
        enrichment_mode=recommended_enrichment_mode,
        output_profile=recommended_output_profile,
    )

    confidence = 0.84 if audit else 0.66
    if audit and (noise_rate > 0.5 or source_success_rate < 0.5):
        confidence = 0.76

    generation_latency_ms = round((perf_counter() - started_at) * 1000.0, 2)

    return PilotAdvice(
        source=source,
        run_id=payload.run_id,
        objective=discovery.objective,
        output_profile=discovery.output_profile,
        experience_profile=experience_plan.profile,
        topology=topology_plan.topology,
        recommended_route=topology_plan.recommended_route,
        clarification_mode=clarification_mode,
        round_budget=round_budget,
        needs_clarification=needs_clarification,
        clarifying_questions=clarifying_questions,
        replan_triggers=replan_triggers,
        stop_conditions=stop_conditions,
        generated_at=datetime.now(UTC),
        generation_latency_ms=generation_latency_ms,
        guidance_summary=guidance_summary,
        recommended_experience_profile=recommended_experience_profile,
        recommended_retrieval_mode=recommended_retrieval_mode,
        recommended_enrichment_mode=recommended_enrichment_mode,
        recommended_output_profile=recommended_output_profile,
        next_steps=next_steps[: payload.max_suggestions],
        next_queries=next_queries[: payload.max_suggestions],
        negative_terms=negative_terms,
        preferred_domains=preferred_domains,
        mode_switches=mode_switches,
        semantic_matches=semantic_matches,
        human_prompt=human_prompt,
        agent_prompt=agent_prompt,
        confidence=confidence,
        notes=notes,
    )


def _resolve_discovery_context(payload: PilotRequest, path: str | None = None) -> tuple[dict[str, Any] | None, DiscoveryRequest]:
    if payload.discovery is not None:
        return None, payload.discovery
    if payload.run_id is None:
        raise ValueError("pilot advice requires either run_id or discovery payload")
    detail = get_run(payload.run_id, path=path) if path is not None else get_run(payload.run_id)
    if detail is None:
        raise KeyError(f"run not found: {payload.run_id}")
    return detail, DiscoveryRequest.model_validate(detail["request"])


def _apply_pilot_overrides(discovery: DiscoveryRequest, payload: PilotRequest) -> DiscoveryRequest:
    intent = discovery.intent
    updated_intent = intent.model_copy(
        update={
            "market": payload.market or intent.market,
            "industry": payload.industry or intent.industry,
        }
    )
    updated = discovery.model_copy(update={"intent": updated_intent})
    if payload.objective:
        updated = updated.model_copy(update={"objective": payload.objective})
    return updated


def _extract_domains(constraints: dict[str, Any]) -> list[str]:
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


def _build_next_queries(discovery: DiscoveryRequest, preferred_domains: list[str], max_suggestions: int) -> list[str]:
    intent = discovery.intent
    base_terms = [intent.market, intent.industry, intent.product or intent.role or ""]
    base_terms = [term for term in base_terms if term]
    narrowed = " ".join(base_terms + intent.extra_keywords[:2]).strip()
    exact_terms = " ".join(filter(None, [intent.product, intent.role, intent.market])).strip()

    queries = [
        narrowed,
        f"\"{exact_terms}\"" if exact_terms else narrowed,
    ]
    if intent.role:
        queries.append(" ".join(filter(None, [intent.market, intent.role, "lead", "contact"])).strip())
    if discovery.objective == "find_events":
        queries.append(" ".join(filter(None, [intent.market, "event", "conference", "summit"])).strip())
    elif discovery.objective == "find_companies":
        queries.append(" ".join(filter(None, [intent.market, "company", "profile"])).strip())
    elif discovery.objective == "find_partnership_signals":
        queries.append(" ".join(filter(None, [intent.market, "partner", "sponsor", "collaboration"])).strip())
    elif discovery.objective == "find_market_activity":
        queries.append(" ".join(filter(None, [intent.market, "activity", "signal", "update"])).strip())

    if preferred_domains:
        queries.append(f"site:{preferred_domains[0]} {narrowed}".strip())

    return [query for query in dict.fromkeys(query for query in queries if query)][:max_suggestions]


def _build_guidance_summary(
    discovery: DiscoveryRequest,
    experience_profile: str,
    topology: str,
    recommended_route: str,
    round_budget: int,
    clarification_mode: str,
    needs_clarification: bool,
    retrieval_mode: str,
    enrichment_mode: str,
    source_success_rate: float,
    noise_rate: float,
    qualified_rate: float,
) -> str:
    clarify_text = "需要先問澄清問題" if needs_clarification else "可直接執行"
    return (
        f"本次 topology 判定為 `{topology}`，建議 route `{recommended_route}`；"
        f"以 `{experience_profile}` 為主航路，預計跑 `{round_budget}` 輪，"
        f"clarification mode `{clarification_mode}`，{clarify_text}。"
        f"檢索模式建議 `{retrieval_mode}`，"
        f"富化模式建議 `{enrichment_mode}`。"
        f"來源成功率約 {source_success_rate:.2f}，噪音率約 {noise_rate:.2f}，"
        f"qualified rate 約 {qualified_rate:.2f}。"
        f"如果要更準，先用 dive 收斂；如果要更廣，再切 radar；"
        f"若來源不穩，保留 wall_guarded 做保底。"
    )


def _build_human_prompt(
    discovery: DiscoveryRequest,
    experience_profile: str,
    topology: str,
    recommended_route: str,
    round_budget: int,
    clarification_mode: str,
    needs_clarification: bool,
    clarifying_questions: list[ClarificationQuestion],
    replan_triggers: list[str],
    stop_conditions: list[str],
    next_steps: list[str],
    next_queries: list[str],
    preferred_domains: list[str],
    negative_terms: list[str],
    retrieval_mode: str,
    enrichment_mode: str,
) -> str:
    lines = [
        f"Topology: `{topology}`，推薦 route: `{recommended_route}`。",
        f"這次建議走 `{experience_profile}` 航路，預計 `{round_budget}` 輪。",
        f"檢索模式：`{retrieval_mode}`；富化模式：`{enrichment_mode}`。",
        f"clarification mode：`{clarification_mode}`；是否先問：`{needs_clarification}`。",
    ]
    if preferred_domains:
        lines.append(f"優先站點：{', '.join(preferred_domains)}。")
    if negative_terms:
        lines.append(f"排除詞：{', '.join(negative_terms)}。")
    if clarifying_questions:
        lines.append("澄清問題：")
        lines.extend([f"- {question.question}" for question in clarifying_questions[:3]])
    if replan_triggers:
        lines.append("Replan 條件：")
        lines.extend([f"- {item}" for item in replan_triggers[:3]])
    if stop_conditions:
        lines.append("停止條件：")
        lines.extend([f"- {item}" for item in stop_conditions[:4]])
    lines.append("下一步可試的查詢：")
    lines.extend([f"- {query}" for query in next_queries[:3]])
    lines.append("建議動作：")
    lines.extend([f"- {step}" for step in next_steps[:3]])
    return "\n".join(lines)


def _build_semantic_matches(discovery: DiscoveryRequest, limit: int, path: str | None = None) -> list[dict[str, Any]]:
    semantic_query = _build_semantic_query(discovery)
    if not semantic_query:
        return []
    matches, _total = search_query_family_memory(
        query=semantic_query,
        objective=discovery.objective,
        limit=limit,
        path=path,
    )
    return [
        {
            "score": score,
            "vector_id": vector_id,
            "query_family": memory.model_dump(mode="json"),
            "memory": memory.model_dump(mode="json"),
            "matched_text": memory.query,
            "backend_used": backend_used,
        }
        for memory, score, vector_id, backend_used in matches
    ]


def _build_semantic_query(discovery: DiscoveryRequest) -> str:
    parts = [
        discovery.objective,
        discovery.intent.market,
        discovery.intent.industry,
        discovery.intent.product,
        discovery.intent.role,
        *discovery.intent.extra_keywords,
        *discovery.intent.negative_keywords,
    ]
    constraints = discovery.intent.constraints or {}
    for key in ("preferred_domains", "site_domains", "domains"):
        value = constraints.get(key)
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, list):
            parts.extend(str(item) for item in value)
    return " ".join(part for part in parts if part)


def _build_agent_prompt(
    discovery: DiscoveryRequest,
    experience_profile: str,
    topology: str,
    recommended_route: str,
    round_budget: int,
    clarification_mode: str,
    needs_clarification: bool,
    clarifying_questions: list[ClarificationQuestion],
    replan_triggers: list[str],
    stop_conditions: list[str],
    next_steps: list[str],
    next_queries: list[str],
    preferred_domains: list[str],
    negative_terms: list[str],
    retrieval_mode: str,
    enrichment_mode: str,
    output_profile: str,
) -> str:
    payload = {
        "objective": discovery.objective,
        "experience_profile": experience_profile,
        "topology": topology,
        "recommended_route": recommended_route,
        "round_budget": round_budget,
        "clarification_mode": clarification_mode,
        "needs_clarification": needs_clarification,
        "clarifying_questions": [question.model_dump(mode="json") for question in clarifying_questions[:3]],
        "replan_triggers": replan_triggers,
        "stop_conditions": stop_conditions,
        "output_profile": output_profile,
        "retrieval_mode": retrieval_mode,
        "enrichment_mode": enrichment_mode,
        "preferred_domains": preferred_domains,
        "negative_terms": negative_terms,
        "next_queries": next_queries,
        "next_steps": next_steps,
    }
    return json_dumps(payload)


def json_dumps(data: Any) -> str:
    import json

    return json.dumps(data, ensure_ascii=False, indent=2)


def _resolve_pricing_quote(pricing: MatePricing):
    if pricing.usd_per_1k_tokens is not None:
        return None
    if pricing.provider_name and pricing.provider_name.lower() in {"local", "omlx", "ollama", "llama.cpp", "local-llm"}:
        return None
    return resolve_pricing_quote(
        provider_name=pricing.provider_name,
        model_name=pricing.model_name,
        catalog_url=pricing.pricing_catalog_url,
        catalog_path=pricing.pricing_catalog_path,
    )
