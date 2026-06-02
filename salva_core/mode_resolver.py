from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from salva_core.presets import resolve_preset_profile
from salva_core.schemas import DiscoveryRequest, ExperiencePlan, ExperiencePlanExplanation, ExperienceProfile, TopologyRoutePlan
from salva_core.topology import plan_route


def resolve_experience_plan(payload: DiscoveryRequest, topology_plan: TopologyRoutePlan | None = None) -> ExperiencePlan:
    topology_plan = topology_plan or plan_route(payload)
    profile = _choose_profile(payload)
    profile = _adjust_profile_for_topology(profile, topology_plan.topology, payload)
    retrieval_mode = payload.retrieval.mode
    enrichment_mode = payload.enrichment.mode
    notes: list[str] = []
    mode_switches: list[str] = []

    if profile == "quick_scan":
        notes.append("lightweight_answer_path")
        mode_switches.append("favor_short_queries")
    elif profile == "lead_focus":
        notes.append("precision_oriented_path")
        mode_switches.append("favor_title_and_snippet")
    elif profile == "event_discovery":
        notes.append("recall_oriented_path")
        mode_switches.append("favor_source_diversity")
    elif profile == "company_research":
        notes.append("balanced_profile_path")
        mode_switches.append("favor_company_and_source_context")
    elif profile == "deep_investigation":
        notes.append("deep_merge_path")
        mode_switches.append("favor_multi_round_context")
    elif profile == "platform_integrator":
        notes.append("integration_first_path")
        mode_switches.append("favor_provider_and_contract_visibility")

    if payload.retrieval.providers:
        notes.append("custom_provider_chain_present")
        mode_switches.append("preserve_provider_overrides")
        profile = "platform_integrator" if profile in {"quick_scan", "lead_focus"} else profile

    if payload.intent.constraints.get("site_domains") or payload.intent.constraints.get("preferred_domains"):
        notes.append("site_specific_intent")
        mode_switches.append("favor_site_specific_search")
        if profile == "quick_scan":
            profile = "company_research"

    if payload.max_results >= 100:
        notes.append("high_recall_budget")
        mode_switches.append("expand_query_family_coverage")
        if profile == "quick_scan":
            profile = "event_discovery"

    notes.append(f"topology={topology_plan.topology}")
    mode_switches.append(f"probe_route={topology_plan.recommended_route}")

    return ExperiencePlan(
        profile=profile,
        objective=payload.objective,
        primary_ux=_primary_ux_label(profile),
        retrieval_mode=retrieval_mode,
        enrichment_mode=enrichment_mode,
        output_profile=payload.output_profile,
        topology=topology_plan.topology,
        topology_confidence=topology_plan.confidence,
        notes=notes,
        mode_switches=mode_switches,
    )


def explain_experience_plan(
    payload: DiscoveryRequest,
    caller_preset: str | None = None,
    topology_plan: TopologyRoutePlan | None = None,
) -> ExperiencePlanExplanation:
    plan = resolve_experience_plan(payload, topology_plan=topology_plan)
    rationale = [f"objective={payload.objective}", f"profile={plan.profile}"]
    rationale.extend(plan.notes)
    rationale.extend(plan.mode_switches)
    prompt_patch = _prompt_patch_for_profile(plan.profile, caller_preset)
    next_steps = _next_steps_for_profile(plan.profile, caller_preset)
    summary = _summary_for_profile(plan.profile, caller_preset, plan.primary_ux)
    return ExperiencePlanExplanation(
        caller_preset=caller_preset,
        generated_at=datetime.now(UTC),
        discovery=payload,
        plan=plan,
        summary=summary,
        rationale=rationale,
        prompt_patch=prompt_patch,
        next_steps=next_steps,
    )


def _choose_profile(payload: DiscoveryRequest) -> ExperienceProfile:
    if payload.objective == "find_events":
        return cast(ExperienceProfile, "event_discovery")
    if payload.objective == "find_exhibitors":
        return cast(ExperienceProfile, "event_discovery")
    if payload.objective == "find_partnership_signals":
        return cast(ExperienceProfile, "deep_investigation")
    if payload.objective == "find_companies":
        return cast(ExperienceProfile, "company_research")
    if payload.objective == "find_market_activity":
        return cast(ExperienceProfile, "deep_investigation")
    if payload.output_profile in {"company_profile", "crm_contact"}:
        return cast(ExperienceProfile, "platform_integrator")
    if payload.intent.role or payload.intent.product:
        return cast(ExperienceProfile, "lead_focus")
    return cast(ExperienceProfile, "quick_scan")


def _adjust_profile_for_topology(profile: ExperienceProfile, topology: str, payload: DiscoveryRequest) -> ExperienceProfile:
    if topology in {"broad", "distributed", "mixed"}:
        if profile == "quick_scan":
            return cast(ExperienceProfile, "deep_investigation")
        if payload.objective == "find_events":
            return cast(ExperienceProfile, "event_discovery")
        return cast(ExperienceProfile, "deep_investigation")
    if topology == "semantic_union":
        return cast(ExperienceProfile, "deep_investigation")
    if topology == "structured":
        if payload.output_profile in {"company_profile", "crm_contact"}:
            return cast(ExperienceProfile, "platform_integrator")
        if profile == "quick_scan":
            return cast(ExperienceProfile, "company_research")
    if topology == "vertical":
        if payload.output_profile in {"company_profile", "crm_contact"}:
            return cast(ExperienceProfile, "platform_integrator")
        if profile == "quick_scan" and (payload.intent.role or payload.intent.product):
            return cast(ExperienceProfile, "lead_focus")
    if topology == "concentrated":
        if profile == "quick_scan":
            return cast(ExperienceProfile, "lead_focus")
    return profile


def _primary_ux_label(profile: str) -> str:
    return {
        "quick_scan": "快速回答",
        "lead_focus": "線索聚焦",
        "event_discovery": "活動發現",
        "company_research": "公司研究",
        "deep_investigation": "深度調查",
        "platform_integrator": "平台整合",
    }[profile]


def _prompt_patch_for_profile(profile: str, caller_preset: str | None) -> list[str]:
    preset_hint = []
    if caller_preset:
        preset_hint.append(f"caller_preset={caller_preset}")
        preset = resolve_preset_profile(caller_preset)
        if preset is not None:
            preset_hint.extend(preset.prompt_patch)

    profile_patch = {
        "quick_scan": [
            "Keep the prompt short and ask for one decisive query family.",
            "Prefer a single high-signal pass before expanding scope.",
        ],
        "lead_focus": [
            "Bias toward title, role, and product signals.",
            "Prefer exact or near-exact phrase matching before broad expansion.",
        ],
        "event_discovery": [
            "Add date windows, venue names, and platform-specific event terms.",
            "Favor source diversity over depth in the first pass.",
        ],
        "company_research": [
            "Ask for company pages, docs, partnerships, funding, and hiring signals.",
            "Use balanced recall with controlled site constraints.",
        ],
        "deep_investigation": [
            "Request multi-round retrieval and evidence retention.",
            "Prefer fallback-aware, multi-provider probing with strict dedupe.",
        ],
        "platform_integrator": [
            "Expose provider and contract details explicitly.",
            "Prefer integration visibility over narrow content focus.",
        ],
    }[profile]
    return [*preset_hint, *profile_patch]


def _next_steps_for_profile(profile: str, caller_preset: str | None) -> list[str]:
    steps = {
        "quick_scan": [
            "Run one short discovery pass.",
            "Escalate only if qualified signals stay low.",
        ],
        "lead_focus": [
            "Start with dive, then anchor if the result set is too small.",
            "Add negative terms early when noisy domains appear.",
        ],
        "event_discovery": [
            "Widen source coverage before deep enrichment.",
            "Use pilot to switch to wall_guarded if the source success rate drops.",
        ],
        "company_research": [
            "Keep balanced retrieval and enrich only high-value candidates.",
            "Pull source attempts into the audit before expanding scope.",
        ],
        "deep_investigation": [
            "Use multi-round retrieval and preserve raw evidence snapshots.",
            "Trigger deeper enrichment only after signal quality improves.",
        ],
        "platform_integrator": [
            "Preserve provider overrides and contract visibility.",
            "Prefer explainable profiles over aggressive recall.",
        ],
    }[profile]
    preset = resolve_preset_profile(caller_preset) if caller_preset else None
    if preset is not None and preset.next_steps:
        steps = [*preset.next_steps, *steps]
    if caller_preset == "agent":
        return [f"agent_hint: {step}" for step in steps]
    if caller_preset == "human":
        return [f"user_hint: {step}" for step in steps]
    return steps


def _summary_for_profile(profile: str, caller_preset: str | None, primary_ux: str) -> str:
    caller = f" for {caller_preset}" if caller_preset else ""
    return f"Resolved `{profile}`{caller}: {primary_ux} path with profile-specific route and prompt patch guidance."
