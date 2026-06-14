from __future__ import annotations

from pathlib import Path
from typing import cast

from salva_core.presets import DEFAULT_PRESET_DIR, load_preset_profiles
from salva_core.schemas import RouteCatalogEntry, RouteCatalogResponse

PROFILE_ROUTE_HINTS: dict[str, dict[str, object]] = {
    # provider_kinds: ordered preference list; runtime filters by availability.
    # obscura_stealth: True activates anti-fingerprinting for Obscura fetches.
    # Callers who supply payload.retrieval.providers explicitly always win.
    "quick_scan": {
        "strategy_rotation": ["dive"],
        "provider_kinds": ["ddg_html"],  # no Docker, no JS — fastest path
        "obscura_stealth": False,
        "recommended_call_surfaces": ["POST /v1/discover", "POST /v1/experience-plan"],
        "usage_notes": [
            "Use for one-pass lookups and very short qualification loops.",
            "This is the lowest-cost route and usually stays within one round.",
        ],
    },
    "lead_focus": {
        "strategy_rotation": ["dive", "anchor"],
        # Search-heavy, no JS content fetch — leads are found via index, not page content.
        "provider_kinds": ["searxng", "whoogle", "ddg_html"],
        "obscura_stealth": False,
        "recommended_call_surfaces": ["POST /v1/discover", "POST /v1/jobs", "POST /v1/pilot"],
        "usage_notes": [
            "Use for outreach, qualification, and CRM-oriented discovery.",
            "Start tight, then expand once the first seed is known.",
        ],
    },
    "event_discovery": {
        "strategy_rotation": ["radar", "anchor"],
        # DDG first (fast radar start); Obscura for event pages with JS-gated content.
        "provider_kinds": ["ddg_html", "searxng", "obscura_browser"],
        "obscura_stealth": False,
        "recommended_call_surfaces": ["POST /v1/jobs", "POST /v1/pilot"],
        "usage_notes": [
            "Use when the first pass should prioritize source diversity over exactness.",
            "Best for conferences, meetups, venues, and time-windowed activity.",
        ],
    },
    "company_research": {
        "strategy_rotation": ["dive", "anchor", "radar"],
        # Full stack: index search + JS content fetch for company pages / SPAs.
        "provider_kinds": ["searxng", "ddg_html", "obscura_browser"],
        "obscura_stealth": False,
        "recommended_call_surfaces": ["POST /v1/jobs", "POST /v1/pilot", "POST /v1/mate/{run_id}"],
        "usage_notes": [
            "Use for balanced company profiling and market context.",
            "This is a default research route when the caller needs both recall and structure.",
        ],
    },
    "deep_investigation": {
        "strategy_rotation": ["anchor", "radar", "pirate"],
        # Stealth mode: pirate round hits CF-protected and paywalled sources.
        "provider_kinds": ["searxng", "ddg_html", "obscura_browser"],
        "obscura_stealth": True,
        "recommended_call_surfaces": ["POST /v1/jobs", "POST /v1/pilot", "POST /v1/mate/{run_id}"],
        "usage_notes": [
            "Use when the run should keep expanding until signal quality improves.",
            "The pirate round is document-heavy and intentionally noisy-tolerant.",
        ],
    },
    "platform_integrator": {
        "strategy_rotation": ["dive", "anchor"],
        # Structured output path: no JS noise, stable index providers only.
        "provider_kinds": ["searxng", "ddg_html"],
        "obscura_stealth": False,
        "recommended_call_surfaces": ["POST /v1/experience-plan", "POST /v1/discover", "GET /v1/presets"],
        "usage_notes": [
            "Use when the caller cares about contracts, adapters, and downstream integration.",
            "Prefer explainability and stable schema surfaces over aggressive expansion.",
        ],
    },
}


def build_route_catalog(path: Path | str = DEFAULT_PRESET_DIR) -> RouteCatalogResponse:
    items = [_preset_to_route_entry(preset) for preset in load_preset_profiles(path)]
    return RouteCatalogResponse(items=items, total=len(items), source_dir=str(Path(path)))


def resolve_route_entry(name: str | None, path: Path | str = DEFAULT_PRESET_DIR) -> RouteCatalogEntry | None:
    if not name:
        return None
    for preset in load_preset_profiles(path):
        if preset.name == name or preset.experience_profile == name:
            return _preset_to_route_entry(preset)
    return None


def _preset_to_route_entry(preset) -> RouteCatalogEntry:
    hints = PROFILE_ROUTE_HINTS.get(
        preset.experience_profile,
        {
            "strategy_rotation": ["dive", "anchor", "radar"],
            "recommended_call_surfaces": ["POST /v1/discover", "POST /v1/jobs", "POST /v1/pilot"],
            "usage_notes": [
                "Fallback route for custom presets that inherit one of the canonical experience profiles.",
            ],
        },
    )
    strategy_rotation = cast(list[str], hints["strategy_rotation"])
    recommended_call_surfaces = cast(list[str], hints["recommended_call_surfaces"])
    usage_notes = cast(list[str], hints["usage_notes"])
    return RouteCatalogEntry(
        name=preset.name,
        title=preset.title,
        description=preset.description,
        experience_profile=preset.experience_profile,
        objective=preset.objective,
        output_profile=preset.output_profile,
        retrieval_mode=preset.retrieval_mode,
        enrichment_mode=preset.enrichment_mode,
        strategy_rotation=list(strategy_rotation),
        recommended_call_surfaces=list(recommended_call_surfaces),
        usage_notes=list(usage_notes),
        notes=list(preset.notes),
        source_path=preset.source_path,
    )
