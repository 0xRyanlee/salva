from __future__ import annotations

from typing import Literal

Objective = Literal[
    "find_leads",
    "find_companies",
    "find_events",
    "find_exhibitors",
    "find_market_activity",
    "find_partnership_signals",
]

OutputProfile = Literal[
    "lead",
    "company",
    "event",
    "activity_signal",
    "crm_contact",
    "company_profile",
    "research_report",
]

EnrichmentMode = Literal[
    "disabled",
    "auto",
    "selected",
    "all",
]

PersistenceMode = Literal["none", "audit"]
MemoryReadScope = Literal["none", "campaign_promoted", "campaign_all", "global_legacy"]
MemoryWriteMode = Literal["none", "quarantine", "promote"]
CacheMode = Literal["ephemeral", "content_addressed"]

EnrichmentPluginName = Literal[
    "omlx",
    "site_html",
    "theharvester",
    "amass",
    "spiderfoot",
]

RetrievalMode = Literal[
    "normal",
    "cautious",
    "resilient",
    "wall_guarded",
]

RetrievalProviderKind = Literal[
    "searxng",
    "whoogle",
    "ddgs",
    "ddg_html",
    "marginalia",
    "site_html",
    "obscura_browser",
    "sitemap",
    "rss",
    "searxng_pool",
    "wikidata",
]

ProviderFamily = Literal[
    "search",
    "llm",
    "vector_store",
    "relational_store",
    "osint",
]

ProviderStatus = Literal[
    "available",
    "partial",
    "planned",
]

ExperienceProfile = Literal[
    "quick_scan",
    "lead_focus",
    "event_discovery",
    "company_research",
    "deep_investigation",
    "platform_integrator",
]

ClarificationMode = Literal[
    "rule",
    "agent",
    "llm",
]

RetrievalHealth = Literal["ok", "degraded", "probe_failed"]

TopologyClass = Literal[
    "vertical",
    "broad",
    "concentrated",
    "distributed",
    "semantic_union",
    "structured",
    "unstructured",
    "mixed",
]

JobStatus = Literal[
    "queued",
    "running",
    "completed",
    "failed",
    "cancelled",
]

StreamEventType = Literal[
    "job_queued",
    "job_started",
    "job_completed",
    "job_failed",
    "job_cancelled",
    "run_persisted",
]

EntityType = Literal[
    "lead",
    "company",
    "event",
    "activity_signal",
    "document",
    "source",
    "person",
]

RelationType = Literal[
    "related_to",
    "organized_by",
    "hosted_by",
    "occurs_in",
    "belongs_to_market",
    "has_contact",
    "derived_from",
    "evidence_for",
    "entity_to_entity",
    "entity_to_evidence",
    "entity_to_hyperedge",
    "event_membership",
    "signal_membership",
]
