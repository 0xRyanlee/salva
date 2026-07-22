"""Builds a DiscoveryRequest from a task_set_v1/v2 task dict.

Shared by record_fixtures.py and run_replay.py so both stages build the
identical request -- the retrieval layer is what's frozen; everything a
future experiment might vary (scorer/gate config) lives downstream of this.
"""
from __future__ import annotations

from typing import Any

from salva_core.schemas import (
    DiscoveryIntent,
    DiscoveryRequest,
    EnrichmentPolicy,
    ExecutionContext,
    RetrievalPolicy,
    RetrievalProviderConfig,
)

# Some experience profiles' PROFILE_ROUTE_HINTS (salva_core/routes.py) restrict
# the provider chain to searxng/ddg_html/obscura_browser, none of which are
# reliably reachable outside a fully-provisioned deployment (no local SearXNG,
# public instances rate-limited/DNS-blocked from a sandbox, no Obscura binary).
# ddgs is the provider DDGS_BACKEND_DIAGNOSTIC.md and Arm D already found
# reliable in this kind of environment -- pinned here as a caller-explicit
# override (highest priority in _build_profile_policy) so recording actually
# gets live results. This does not change production defaults or profile
# routing; it only affects requests built by this harness.
_HARNESS_PROVIDERS = [
    RetrievalProviderConfig(kind="ddgs"),
    RetrievalProviderConfig(kind="searxng"),
]


def build_discovery_request(
    task: dict[str, Any],
    *,
    max_results: int = 50,
    qualify_threshold: float | None = None,
) -> DiscoveryRequest:
    intent_payload = task["intent"]
    intent = DiscoveryIntent(
        market=intent_payload["market"],
        industry=intent_payload["industry"],
        product=intent_payload.get("product"),
        role=intent_payload.get("role"),
        extra_keywords=list(intent_payload.get("extra_keywords", [])),
        negative_keywords=list(intent_payload.get("negative_keywords", [])),
        constraints=dict(intent_payload.get("constraints", {})),
    )
    return DiscoveryRequest(
        objective=task["objective"],
        intent=intent,
        max_results=max_results,
        qualify_threshold=qualify_threshold,
        retrieval=RetrievalPolicy(providers=list(_HARNESS_PROVIDERS)),
        # Enrichment (omlx) and persistence are out of scope for the retrieval
        # fixture harness -- disabled so record/replay never touches the LLM
        # enrichment path or the project sqlite DB.
        enrichment=EnrichmentPolicy(mode="disabled"),
        execution=ExecutionContext(persistence="none"),
    )
