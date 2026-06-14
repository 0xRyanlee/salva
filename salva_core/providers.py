from __future__ import annotations

from typing import cast

from retrieval.registry import list_provider_descriptors
from salva_core.llm import list_llm_provider_descriptors
from salva_core.schemas import (
    ProviderCatalogResponse,
    ProviderInterfaceDescriptor,
    ProviderStatus,
)


def build_provider_catalog() -> ProviderCatalogResponse:
    items = [
        *[
            ProviderInterfaceDescriptor(
                family="search",
                kind=descriptor.kind,
                name=descriptor.name,
                description=descriptor.description,
                status="available",
                supports_custom_endpoint=descriptor.supports_custom_endpoint,
                supports_health_check=False,
                supports_local_mode=True,
                enabled_by_default=descriptor.enabled_by_default,
                env_vars=descriptor.env_vars,
                notes=[
                    "Part of the built-in retrieval router.",
                    "Can be overridden per request via retrieval.providers.",
                ],
            )
            for descriptor in list_provider_descriptors()
        ],
        *[
            ProviderInterfaceDescriptor(
                family="llm",
                kind=descriptor.kind,
                name=descriptor.name,
                description=descriptor.description,
                status="available",
                supports_custom_endpoint=descriptor.supports_custom_endpoint,
                supports_health_check=descriptor.supports_health_check,
                supports_local_mode=True,
                enabled_by_default=True,
                env_vars=descriptor.env_vars,
                notes=[
                    "Used for bounded extraction, summarization, expansion, and output shaping.",
                ],
            )
            for descriptor in list_llm_provider_descriptors()
        ],
        ProviderInterfaceDescriptor(
            family="vector_store",
            kind="semantic_plane",
            name="Local Semantic Plane",
            description="Local semantic memory plane used for query-family vector search and reuse.",
            status="available",
            supports_custom_endpoint=False,
            supports_health_check=False,
            supports_local_mode=True,
            enabled_by_default=True,
            env_vars=[],
            notes=[
                "Backed by local persistence today; can be replaced by a vector backend later.",
                "Currently powers query-family semantic recall.",
            ],
        ),
        ProviderInterfaceDescriptor(
            family="relational_store",
            kind="sqlite_hold_store",
            name="SQLite Hold Store",
            description="Local relational store used for runs, telemetry, evidence, relations, and hyperedges.",
            status="available",
            supports_custom_endpoint=False,
            supports_health_check=False,
            supports_local_mode=True,
            enabled_by_default=True,
            env_vars=[],
            notes=[
                "Acts as the canonical runtime store in local mode.",
                "Can later be projected to PostgreSQL or another relational backend.",
            ],
        ),
        *[
            ProviderInterfaceDescriptor(
                family="osint",
                kind=kind,
                name=name,
                description=description,
                status=cast(ProviderStatus, status),
                supports_custom_endpoint=False,
                supports_health_check=False,
                supports_local_mode=True,
                enabled_by_default=False,
                env_vars=env_vars,
                notes=notes,
            )
            for kind, name, description, status, env_vars, notes in [
                (
                    "theharvester",
                    "theHarvester",
                    "Built-in OSINT enrichment adapter for collecting public emails, hosts, and names when the CLI is installed.",
                    "partial",
                    ["THEHARVESTER_COMMAND"],
                    ["Availability depends on a local theHarvester installation."],
                ),
                (
                    "amass",
                    "Amass",
                    "Built-in OSINT enrichment adapter for domain and asset discovery when the CLI is installed.",
                    "partial",
                    ["AMASS_COMMAND"],
                    ["Availability depends on a local Amass installation."],
                ),
                (
                    "spiderfoot",
                    "SpiderFoot",
                    "Built-in OSINT enrichment adapter for JSON-based target scans when SpiderFoot is installed locally.",
                    "partial",
                    ["SPIDERFOOT_COMMAND", "SPIDERFOOT_SF_PY"],
                    ["Availability depends on a local SpiderFoot installation."],
                ),
            ]
        ],
    ]
    return ProviderCatalogResponse(items=items, total=len(items))
