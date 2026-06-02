from __future__ import annotations

import json
import os
from pathlib import Path

from salva_core.schemas import (
    PresetCatalogResponse,
    PresetProfile,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PRESET_DIR = Path(os.getenv("SALVA_PRESET_DIR", str(PROJECT_ROOT / "configs" / "presets")))


def build_builtin_presets() -> list[PresetProfile]:
    return [
        PresetProfile(
            name="quick_scan",
            title="Quick Scan",
            description="A low-friction preset for one-pass discovery and fast qualification.",
            experience_profile="quick_scan",
            objective="find_leads",
            output_profile="lead",
            retrieval_mode="normal",
            enrichment_mode="auto",
            prompt_patch=[
                "Keep the query family small and decisive.",
                "Prefer a single high-signal pass before expanding scope.",
            ],
            next_steps=[
                "Run one short discovery pass.",
                "Escalate only if qualified signals stay low.",
            ],
            notes=["Useful for tight time budgets and first-pass scans."],
        ),
        PresetProfile(
            name="lead_focus",
            title="Lead Focus",
            description="A precision-oriented preset for outreach, qualification, and CRM sync.",
            experience_profile="lead_focus",
            objective="find_leads",
            output_profile="lead",
            retrieval_mode="resilient",
            enrichment_mode="auto",
            preferred_domains=["linkedin.com", "crunchbase.com", "clutch.co"],
            prompt_patch=[
                "Bias toward title, role, and product signals.",
                "Prefer exact or near-exact phrase matching before broad expansion.",
            ],
            next_steps=[
                "Start with dive, then anchor if the result set is too small.",
                "Add negative terms early when noisy domains appear.",
            ],
            notes=["Best for lead discovery and outreach preparation."],
        ),
        PresetProfile(
            name="event_discovery",
            title="Event Discovery",
            description="A recall-oriented preset for activities, conferences, and venue-driven exploration.",
            experience_profile="event_discovery",
            objective="find_events",
            output_profile="event",
            retrieval_mode="cautious",
            enrichment_mode="auto",
            preferred_domains=["facebook.com", "lu.ma", "eventbrite.com", "meetup.com"],
            prompt_patch=[
                "Add date windows, venue names, and platform-specific event terms.",
                "Favor source diversity over depth in the first pass.",
            ],
            next_steps=[
                "Widen source coverage before deep enrichment.",
                "Use pilot to switch to wall_guarded if the source success rate drops.",
            ],
            notes=["Useful for conference, webinar, and meetup discovery."],
        ),
        PresetProfile(
            name="company_research",
            title="Company Research",
            description="A balanced preset for company profiles, partners, and market context.",
            experience_profile="company_research",
            objective="find_companies",
            output_profile="company_profile",
            retrieval_mode="resilient",
            enrichment_mode="auto",
            preferred_domains=["linkedin.com", "facebook.com", "eventbrite.com", "medium.com"],
            prompt_patch=[
                "Ask for company pages, docs, partnerships, funding, and hiring signals.",
                "Use balanced recall with controlled site constraints.",
            ],
            next_steps=[
                "Keep balanced retrieval and enrich only high-value candidates.",
                "Pull source attempts into the audit before expanding scope.",
            ],
            notes=["Balanced profile for internal research and profile export."],
        ),
        PresetProfile(
            name="deep_investigation",
            title="Deep Investigation",
            description="A high-recall preset for multi-round probing, evidence retention, and fallback-aware search.",
            experience_profile="deep_investigation",
            objective="find_partnership_signals",
            output_profile="activity_signal",
            retrieval_mode="wall_guarded",
            enrichment_mode="all",
            prompt_patch=[
                "Request multi-round retrieval and evidence retention.",
                "Prefer fallback-aware, multi-provider probing with strict dedupe.",
            ],
            next_steps=[
                "Use multi-round retrieval and preserve raw evidence snapshots.",
                "Trigger deeper enrichment only after signal quality improves.",
            ],
            notes=["For noisy domains, ambiguous relationships, and audit-heavy work."],
        ),
        PresetProfile(
            name="platform_integrator",
            title="Platform Integrator",
            description="A contract-first preset for agents and downstream platform consumers.",
            experience_profile="platform_integrator",
            objective="find_companies",
            output_profile="company_profile",
            retrieval_mode="resilient",
            enrichment_mode="selected",
            prompt_patch=[
                "Expose provider and contract details explicitly.",
                "Prefer integration visibility over narrow content focus.",
            ],
            next_steps=[
                "Preserve provider overrides and contract visibility.",
                "Prefer explainable profiles over aggressive recall.",
            ],
            notes=["Best when the caller cares about contracts, adapters, and APIs."],
        ),
    ]


def load_preset_profiles(path: Path | str = DEFAULT_PRESET_DIR) -> list[PresetProfile]:
    preset_path = Path(path)
    if preset_path.exists():
        items: list[PresetProfile] = []
        for file_path in sorted(preset_path.glob("*.json")):
            try:
                payload = json.loads(file_path.read_text(encoding="utf-8"))
                item = PresetProfile.model_validate(payload)
                item = item.model_copy(update={"source_path": str(file_path)})
                items.append(item)
            except Exception:
                continue
        if items:
            return items
    return build_builtin_presets()


def build_preset_catalog(path: Path | str = DEFAULT_PRESET_DIR) -> PresetCatalogResponse:
    items = load_preset_profiles(path)
    return PresetCatalogResponse(items=items, total=len(items), source_dir=str(Path(path)))


def resolve_preset_profile(name: str | None, path: Path | str = DEFAULT_PRESET_DIR) -> PresetProfile | None:
    if not name:
        return None
    for item in load_preset_profiles(path):
        if item.name == name or item.experience_profile == name:
            return item
    return None
