from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

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
]

StreamEventType = Literal[
    "job_queued",
    "job_started",
    "job_completed",
    "job_failed",
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


class DomainHints(BaseModel):
    """
    Caller-supplied vocabulary extensions injected per-request.

    These are merged on top of the registry vocab for the resolved domain,
    extending (not replacing) built-in synonym_groups, signal_terms, and
    source_hints. Use this to add domain-specific knowledge without modifying
    server-side code.

    Example — legal tech search:
        {
          "synonym_groups": {"contract": ["NDA", "SLA", "agreement", "MOU"]},
          "signal_terms":   ["compliance", "e-signature", "regulatory"],
          "source_hints":   ["law360.com", "legaltech.com"]
        }
    """
    synonym_groups:  dict[str, list[str]] = Field(default_factory=dict)
    region_variants: dict[str, list[str]] = Field(default_factory=dict)
    signal_terms:    list[str]            = Field(default_factory=list)
    source_hints:    list[str]            = Field(default_factory=list)
    noise_terms:     list[str]            = Field(default_factory=list)


class DiscoveryIntent(BaseModel):
    market: str = Field(..., description="Target market or region.")
    industry: str = Field(..., description="Target industry or vertical.")
    product: str | None = Field(default=None, description="Optional product or segment.")
    role: str | None = Field(default=None, description="Optional target role.")
    extra_keywords: list[str] = Field(default_factory=list)
    negative_keywords: list[str] = Field(default_factory=list)
    constraints: dict[str, Any] = Field(default_factory=dict)
    domain_hints: DomainHints | None = Field(
        default=None,
        description=(
            "Optional caller-supplied vocabulary extensions. Merged on top of the "
            "registry vocab for the resolved domain. Use to inject domain-specific "
            "synonym groups, signal terms, or source hints without modifying server code."
        ),
    )


class TransformOptions(BaseModel):
    fields: list[str] | None = None
    rename: dict[str, str] = Field(default_factory=dict)
    drop_nulls: bool = True


class OutputTransformFieldSpec(BaseModel):
    name: str
    source: str | None = None
    description: str
    required: bool = False
    examples: list[str] = Field(default_factory=list)


class OutputTransformProfileSpec(BaseModel):
    profile: OutputProfile
    description: str
    caller_types: list[str] = Field(default_factory=list)
    fields: list[OutputTransformFieldSpec] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class OutputTransformCatalog(BaseModel):
    items: list[OutputTransformProfileSpec] = Field(default_factory=list)
    total: int = 0


class RetrievalPolicy(BaseModel):
    mode: RetrievalMode = "resilient"
    local_first: bool = True
    allow_public_fallback: bool = True
    prefer_builtin_instances: bool = True
    request_timeout: float = 15.0
    request_delay: float = 0.5
    cooldown_seconds: float = 90.0
    max_instances_per_query: int = 4
    html_fallback: bool = True
    engine_rotation: bool = True
    region_hint: str | None = None
    extra_instances: list[str] = Field(default_factory=list)
    site_domains: list[str] = Field(default_factory=list)
    providers: list[RetrievalProviderConfig] = Field(default_factory=list)
    proxy_url: str | None = None
    obscura_stealth: bool = False


class RetrievalProviderConfig(BaseModel):
    kind: RetrievalProviderKind
    base_url: str | None = None
    enabled: bool = True
    request_timeout: float | None = None
    request_delay: float | None = None
    cooldown_seconds: float | None = None
    max_instances_per_query: int | None = None
    allow_public_fallback: bool | None = None
    prefer_builtin_instances: bool | None = None
    html_fallback: bool | None = None
    engine_rotation: bool | None = None
    site_domains: list[str] = Field(default_factory=list)
    extra_instances: list[str] = Field(default_factory=list)
    note: str | None = None


class EnrichmentPolicy(BaseModel):
    mode: EnrichmentMode = "auto"
    enabled_plugins: list[EnrichmentPluginName] = Field(default_factory=list)
    max_targets: int = 8
    parallelism: int = 4
    auto_merge: bool = True
    omlx_timeout: float = 45.0  # Timeout for OMLX enrichment calls (seconds)
    omlx_max_retries: int = 3  # Maximum retry attempts for failed calls


class MemoryPolicy(BaseModel):
    read_scope: MemoryReadScope = "none"
    write_mode: MemoryWriteMode = "quarantine"
    min_success_score: float = Field(default=0.3, ge=0.0, le=1.0)


_DEFAULT_STABILITY_METHODS: tuple[Literal["drift", "volatility"], ...] = ("drift", "volatility")


class StabilityPolicy(BaseModel):
    """Opt-in domain-level stability gating for semantic memory scoring.

    See salva_core/stability.py for the drift/volatility computation and
    processing/scorer.py::ScorerConfig.w_stability for how it feeds into the
    composite score. Disabled by default -- enabling it has zero effect on
    scoring until a caller explicitly sets enabled=True.
    """

    enabled: bool = False
    min_history: int = Field(default=3, ge=1)
    penalty_strength: float = Field(default=0.15, ge=0.0, le=1.0)
    methods: list[Literal["drift", "volatility"]] = Field(
        default_factory=lambda: list(_DEFAULT_STABILITY_METHODS),
        description=(
            "Reserved for future per-method selection. compute_stability_signals() "
            "currently always computes both together -- this field is not yet read "
            "anywhere; splitting drift/volatility into independently selectable "
            "signals is a separate follow-up, not implemented by this field's mere "
            "presence."
        ),
    )


class CachePolicy(BaseModel):
    mode: CacheMode = "ephemeral"
    ttl_hours: int = Field(default=24, ge=1, le=24 * 365)
    retain_artifacts: bool = False

    @model_validator(mode="after")
    def _reject_unimplemented_mode(self) -> CachePolicy:
        if self.mode != "ephemeral":
            raise ValueError("content_addressed cache is not implemented")
        return self


class ExecutionContext(BaseModel):
    project_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
        description="Project scope for run/job isolation. Runs with different project_ids are logically isolated.",
    )
    campaign_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
        description="Agent-declared research scope. Salva enforces memory isolation within it.",
    )
    continuation_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
        description="Optional research-thread identifier reused across related runs.",
    )
    persistence: PersistenceMode = "audit"
    memory: MemoryPolicy = Field(default_factory=MemoryPolicy)
    cache: CachePolicy = Field(default_factory=CachePolicy)
    tags: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_memory_scope(self) -> ExecutionContext:
        if self.memory.read_scope in {"campaign_promoted", "campaign_all"} and not self.campaign_id:
            raise ValueError(f"{self.memory.read_scope} requires campaign_id")
        if self.memory.write_mode == "promote" and not self.campaign_id:
            raise ValueError("memory.write_mode=promote requires campaign_id")
        if self.persistence == "none" and self.memory.write_mode != "none":
            self.memory = self.memory.model_copy(update={"write_mode": "none"})
        return self


class EvidenceItem(BaseModel):
    source_url: str
    source_name: str | None = None
    title: str | None = None
    snippet: str | None = None
    captured_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidenceRecord(BaseModel):
    evidence_id: str
    run_id: str
    entity_id: str
    source_url: str
    source_name: str | None = None
    title: str | None = None
    snippet: str | None = None
    captured_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidenceChainLink(BaseModel):
    evidence_id: str
    source_url: str
    source_name: str | None = None
    title: str | None = None
    snippet: str | None = None
    captured_at: datetime | None = None
    relation_ids: list[str] = Field(default_factory=list)
    hyperedge_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidenceChainRecord(BaseModel):
    entity_id: str
    entity_title: str | None = None
    run_id: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    relation_ids: list[str] = Field(default_factory=list)
    hyperedge_ids: list[str] = Field(default_factory=list)
    links: list[EvidenceChainLink] = Field(default_factory=list)
    first_captured_at: datetime | None = None
    last_captured_at: datetime | None = None
    evidence_count: int = 0
    relation_count: int = 0
    hyperedge_count: int = 0
    notes: list[str] = Field(default_factory=list)


class HoldHyperedgeMember(BaseModel):
    member_id: str
    member_kind: str
    role: str
    weight: float = 1.0
    evidence_ids: list[str] = Field(default_factory=list)


class HoldHyperedgeRecord(BaseModel):
    hyperedge_id: str
    run_id: str
    hyperedge_type: str
    summary: str | None = None
    confidence: float = 0.0
    members: list[HoldHyperedgeMember] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None


class CanonicalRelation(BaseModel):
    relation_id: str
    schema_name: str = "canonical_relation"
    schema_version: str = "0.1.0"
    storage_version: str = "0.1.0"
    migration_version: str = "0.1.0"
    relation_type: RelationType
    from_entity_id: str
    to_entity_id: str
    confidence: float = 0.0
    evidence_ids: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)


class EventDetails(BaseModel):
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    timezone: str | None = None
    location_name: str | None = None
    location_address: str | None = None
    city: str | None = None
    country: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    organizer_name: str | None = None
    organizer_email: str | None = None
    organizer_domain: str | None = None
    capacity: int | None = None
    price_amount: float | None = None
    currency: str | None = None
    cover_image_url: str | None = None
    speaker_names: list[str] = Field(default_factory=list)
    venue_name: str | None = None


class RelationRecord(BaseModel):
    relation_id: str
    run_id: str
    schema_name: str = "canonical_relation"
    schema_version: str = "0.1.0"
    storage_version: str = "0.1.0"
    migration_version: str = "0.1.0"
    relation_type: RelationType
    from_entity_id: str
    to_entity_id: str
    confidence: float = 0.0
    evidence_ids: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None


class RelationsResponse(BaseModel):
    items: list[RelationRecord]
    total: int


class RelationQueryRequest(BaseModel):
    run_id: str | None = None
    relation_type: RelationType | None = None
    from_entity_id: str | None = None
    to_entity_id: str | None = None
    limit: int = Field(default=200, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class CanonicalEntity(BaseModel):
    entity_id: str
    entity_type: EntityType
    title: str
    summary: str | None = None
    market: str | None = None
    industry: str | None = None
    tags: list[str] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    confidence: float = 0.0
    score: float = 0.0
    status: str = "new"
    event: EventDetails | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class TelemetryRecord(BaseModel):
    query: str
    round_num: int
    strategy: str
    results_total: int = 0
    results_qualified: int = 0
    avg_score: float = 0.0
    reject_reasons: list[str] = Field(default_factory=list)
    noise_domains: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class FeedbackRecord(BaseModel):
    entity_id: str
    feedback_type: Literal["accept", "partial_accept", "reject", "contacted", "converted"]
    note: str | None = None
    created_at: datetime | None = None


class DiscoveryRequest(BaseModel):
    objective: Objective
    intent: DiscoveryIntent
    tenant_id: str | None = Field(
        default=None,
        description="Optional tenant/workspace identifier for usage aggregation and quota tracking.",
    )
    output_profile: OutputProfile = "lead"
    transform: TransformOptions = Field(default_factory=TransformOptions)
    retrieval: RetrievalPolicy = Field(default_factory=RetrievalPolicy)
    enrichment: EnrichmentPolicy = Field(default_factory=EnrichmentPolicy)
    execution: ExecutionContext = Field(default_factory=ExecutionContext)
    stability: StabilityPolicy | None = Field(
        default=None,
        description=(
            "Opt-in stability gating (see StabilityPolicy). None/absent behaves "
            "identically to StabilityPolicy(enabled=False) -- disabled by default."
        ),
    )
    max_results: int = Field(default=50, ge=1, le=500)
    qualify_threshold: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "Explicit override for the qualification gate. None (default) means "
            "use the domain-calibrated threshold from "
            "QualificationScorer.domain_threshold(intent.domain) -- e.g. 0.35 for "
            "bd_leads/taiwan_hardware/partnerships, 0.40 elsewhere. Set explicitly "
            "to force a specific threshold regardless of domain."
        ),
    )


class TopologyProbeRequest(BaseModel):
    discovery: DiscoveryRequest
    caller_preset: str | None = None
    probe_budget: int = Field(default=4, ge=1, le=8)


class TopologyProbeErrorSurface(BaseModel):
    stage: str = "probe"
    code: str
    route: str | None = None
    provider: str | None = None
    topology: TopologyClass | None = None
    query: str | None = None
    message: str
    actionable_hint: str | None = None


class TopologyProbeResult(BaseModel):
    topology: TopologyClass
    confidence: float = 0.0
    probe_queries: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    error_surface: list[TopologyProbeErrorSurface] = Field(default_factory=list)
    retrieval_health: RetrievalHealth = Field(
        default="ok",
        description=(
            "'ok': live probe succeeded with a healthy result, or was not attempted "
            "(disabled, or caller_preset already implies known topology). "
            "'degraded': probe reached a provider but the result was weak or empty; "
            "confidence was lowered and/or topology hard-degraded to 'unstructured'. "
            "'probe_failed': every probe attempt errored at the connection layer -- "
            "topology/confidence reflect the static classifier only, not a confirmed "
            "live result. Callers should not treat probe_failed the same as a "
            "confidently-checked low score."
        ),
    )


class TopologyRoutePlan(BaseModel):
    topology: TopologyClass
    confidence: float = 0.0
    recommended_route: str
    recommended_objective: Objective
    source_pack: list[str] = Field(default_factory=list)
    strategy_bias: list[str] = Field(default_factory=list)
    fanout_policy: str
    merge_policy: str
    probe_queries: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    error_surface: list[TopologyProbeErrorSurface] = Field(default_factory=list)
    route_entry: RouteCatalogEntry | None = None
    retrieval_health: RetrievalHealth = "ok"


class TopologyProbeResponse(BaseModel):
    probe: TopologyProbeResult
    plan: TopologyRoutePlan


class ExperiencePlan(BaseModel):
    profile: ExperienceProfile
    objective: Objective
    primary_ux: str
    retrieval_mode: RetrievalMode
    enrichment_mode: EnrichmentMode
    output_profile: OutputProfile
    topology: TopologyClass | None = None
    topology_confidence: float = 0.0
    notes: list[str] = Field(default_factory=list)
    mode_switches: list[str] = Field(default_factory=list)


class PlannerRequest(BaseModel):
    discovery: DiscoveryRequest | None = None
    objective: Objective | None = None
    intent: DiscoveryIntent | None = None
    output_profile: OutputProfile = "lead"
    tenant_id: str | None = None
    caller_preset: str | None = None
    question_budget: int = Field(default=3, ge=1, le=5)
    allow_llm_preprompt: bool = True

    @model_validator(mode="after")
    def _ensure_discovery(self) -> PlannerRequest:
        if self.discovery is None:
            if self.objective is None or self.intent is None:
                raise ValueError("PlannerRequest requires discovery or objective + intent")
            self.discovery = DiscoveryRequest(
                objective=self.objective,
                intent=self.intent,
                tenant_id=self.tenant_id,
                output_profile=self.output_profile,
            )
        return self


class ClarificationQuestion(BaseModel):
    key: str
    question: str
    rationale: str
    impact: str


class PrepromptResult(BaseModel):
    clarification_needed: bool = False
    clarification_mode: ClarificationMode = "rule"
    ambiguity_score: float = 0.0
    risk_level: Literal["low", "medium", "high"] = "low"
    normalized_goal: dict[str, Any] = Field(default_factory=dict)
    clarifying_questions: list[ClarificationQuestion] = Field(default_factory=list)
    assumptions_if_skip: list[str] = Field(default_factory=list)
    llm_used: bool = False
    llm_model: str | None = None
    llm_message: str | None = None


class ResearchPlan(BaseModel):
    topology: TopologyClass
    recommended_route: str
    experience_profile: ExperienceProfile
    clarification_mode: ClarificationMode = "rule"
    round_budget: int
    round_goals: list[str] = Field(default_factory=list)
    completeness_target: float = 0.0
    confidence_target: float = 0.0
    source_pack: list[str] = Field(default_factory=list)
    strategy_bias: list[str] = Field(default_factory=list)
    fanout_policy: str = "single_shot"
    merge_policy: str = "strict_dedupe"
    replan_triggers: list[str] = Field(default_factory=list)
    stop_conditions: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class PlannerResponse(BaseModel):
    probe: TopologyProbeResult
    route_plan: TopologyRoutePlan
    preprompt: PrepromptResult
    plan: ResearchPlan
    experience_plan: ExperiencePlan


class ExperiencePlanRequest(BaseModel):
    discovery: DiscoveryRequest
    caller_preset: str | None = None


class ExperiencePlanExplanation(BaseModel):
    caller_preset: str | None = None
    generated_at: datetime
    discovery: DiscoveryRequest
    plan: ExperiencePlan
    summary: str
    rationale: list[str] = Field(default_factory=list)
    prompt_patch: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)


class PresetProfile(BaseModel):
    name: str
    title: str
    description: str
    experience_profile: ExperienceProfile
    objective: Objective | None = None
    output_profile: OutputProfile | None = None
    retrieval_mode: RetrievalMode = "resilient"
    enrichment_mode: EnrichmentMode = "auto"
    prompt_patch: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    preferred_domains: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    source_path: str | None = None


class PresetCatalogResponse(BaseModel):
    items: list[PresetProfile] = Field(default_factory=list)
    total: int = 0
    source_dir: str | None = None


class RouteCatalogEntry(BaseModel):
    name: str
    title: str
    description: str
    experience_profile: ExperienceProfile
    objective: Objective | None = None
    output_profile: OutputProfile | None = None
    retrieval_mode: RetrievalMode = "resilient"
    enrichment_mode: EnrichmentMode = "auto"
    strategy_rotation: list[str] = Field(default_factory=list)
    recommended_call_surfaces: list[str] = Field(default_factory=list)
    usage_notes: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    source_path: str | None = None


class RouteCatalogResponse(BaseModel):
    items: list[RouteCatalogEntry] = Field(default_factory=list)
    total: int = 0
    source_dir: str | None = None


class DiscoveryResponse(BaseModel):
    objective: Objective
    output_profile: OutputProfile
    entities: list[CanonicalEntity]
    transformed_items: list[dict[str, Any]] = Field(default_factory=list)
    relations: list[CanonicalRelation] = Field(default_factory=list)
    telemetry: list[TelemetryRecord] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


class RunRecord(BaseModel):
    run_id: str
    objective: str
    output_profile: str
    created_at: datetime
    request: dict[str, Any]
    meta: dict[str, Any]
    project_id: str | None = None
    campaign_id: str | None = None
    continuation_id: str | None = None
    entity_count: int = 0
    relation_count: int = 0


class RunsResponse(BaseModel):
    items: list[RunRecord]
    total: int


class TelemetryResponse(BaseModel):
    items: list[TelemetryRecord]
    total: int


class TenantUsageRecord(BaseModel):
    tenant_id: str
    run_count: int = 0
    job_count: int = 0
    completed_job_count: int = 0
    failed_job_count: int = 0
    queued_job_count: int = 0
    running_job_count: int = 0
    raw_count: int = 0
    qualified_count: int = 0
    telemetry_count: int = 0
    source_attempt_count: int = 0
    latest_run_at: datetime | None = None
    latest_job_at: datetime | None = None
    provider_kinds: list[str] = Field(default_factory=list)


class UsageTelemetryResponse(BaseModel):
    generated_at: datetime
    tenant_id: str | None = None
    total_runs: int = 0
    total_jobs: int = 0
    total_tenants: int = 0
    items: list[TenantUsageRecord] = Field(default_factory=list)


class QuotaPolicy(BaseModel):
    enabled: bool = False
    hourly_run_limit: int | None = None
    daily_run_limit: int | None = None
    hourly_job_limit: int | None = None
    daily_job_limit: int | None = None


class QuotaWindowUsage(BaseModel):
    window: Literal["hourly", "daily"]
    run_count: int = 0
    job_count: int = 0
    run_limit: int | None = None
    job_limit: int | None = None
    run_remaining: int | None = None
    job_remaining: int | None = None


class TenantQuotaResponse(BaseModel):
    tenant_id: str | None = None
    generated_at: datetime
    allowed: bool = True
    policy: QuotaPolicy = Field(default_factory=QuotaPolicy)
    windows: list[QuotaWindowUsage] = Field(default_factory=list)
    violated: list[str] = Field(default_factory=list)


class SourceAttemptRecord(BaseModel):
    run_id: str
    strategy: str
    base_url: str
    mode: str
    source_class: str | None = None
    trust_level: str | None = None
    risk_level: str | None = None
    recommended_crawl_mode: str | None = None
    result_count: int
    succeeded: bool
    error: str | None = None
    format_used: str | None = None


class SourceAttemptsResponse(BaseModel):
    items: list[SourceAttemptRecord]
    total: int


class RunSnapshot(BaseModel):
    run_id: str
    objective: str
    output_profile: str
    created_at: datetime | None = None
    generated_at: datetime
    request: dict[str, Any]
    meta: dict[str, Any] = Field(default_factory=dict)
    entities: list[CanonicalEntity] = Field(default_factory=list)
    relations: list[CanonicalRelation] = Field(default_factory=list)
    evidence_records: list[EvidenceRecord] = Field(default_factory=list)
    evidence_chains: list[EvidenceChainRecord] = Field(default_factory=list)
    hyperedges: list[HoldHyperedgeRecord] = Field(default_factory=list)
    query_family_memory: list[QueryFamilyMemoryRecord] = Field(default_factory=list)
    telemetry: list[TelemetryRecord] = Field(default_factory=list)
    source_attempts: list[SourceAttemptRecord] = Field(default_factory=list)
    plugin_reports: list[PluginReportRecord] = Field(default_factory=list)
    audit: AuditReport | None = None
    entity_count: int = 0
    relation_count: int = 0
    evidence_count: int = 0
    evidence_chain_count: int = 0
    hyperedge_count: int = 0
    query_family_count: int = 0
    telemetry_count: int = 0
    source_attempt_count: int = 0
    plugin_report_count: int = 0


class SnapshotExportRequest(BaseModel):
    output_path: str | None = None


class SnapshotExportResult(BaseModel):
    snapshot: RunSnapshot
    export_path: str
    bytes_written: int
    sha256: str


class EvidenceResponse(BaseModel):
    items: list[EvidenceRecord]
    total: int


class EvidenceChainsRequest(BaseModel):
    run_id: str | None = None
    entity_id: str | None = None
    limit: int = Field(default=200, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class EvidenceChainsResponse(BaseModel):
    items: list[EvidenceChainRecord]
    total: int


class HyperedgesResponse(BaseModel):
    items: list[HoldHyperedgeRecord]
    total: int


class HoldMigrationRecord(BaseModel):
    registry_id: str
    schema_name: str
    hold_version: str
    storage_version: str
    migration_version: str
    migration_strategy: str
    status: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class HoldMigrationsResponse(BaseModel):
    items: list[HoldMigrationRecord]
    total: int


class QueryFamilyMemoryRecord(BaseModel):
    memory_id: str
    run_id: str
    campaign_id: str | None = None
    continuation_id: str | None = None
    memory_status: Literal["legacy", "quarantine", "promoted"] = "legacy"
    promoted_at: datetime | None = None
    domain: str | None = None
    objective: str
    output_profile: str
    round_num: int
    strategy: str
    query: str
    query_signature: str
    source_nodes: list[str] = Field(default_factory=list)
    content_nodes: list[str] = Field(default_factory=list)
    content_weights: dict[str, float] = Field(default_factory=dict)
    source_hints: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    raw_total: int = 0
    qualified_total: int = 0
    avg_score: float = 0.0
    success_score: float = 0.0
    created_at: datetime | None = None


class QueryFamilyMemoryResponse(BaseModel):
    items: list[QueryFamilyMemoryRecord]
    total: int


class BenchmarkRequest(BaseModel):
    run_ids: list[str] = Field(default_factory=list, min_length=1)
    label: str | None = None
    output_path: str | None = None


class BenchmarkRunRecord(BaseModel):
    run_id: str
    objective: str
    output_profile: str
    experience_profile: str
    created_at: datetime | None = None
    metrics: dict[str, float] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
    provider_kinds: list[str] = Field(default_factory=list)


class BenchmarkSeriesPoint(BaseModel):
    key: str
    metrics: dict[str, float] = Field(default_factory=dict)
    count: int = 0


class BenchmarkReport(BaseModel):
    label: str | None = None
    generated_at: datetime
    total_runs: int = 0
    runs: list[BenchmarkRunRecord] = Field(default_factory=list)
    by_experience_profile: list[BenchmarkSeriesPoint] = Field(default_factory=list)
    by_objective: list[BenchmarkSeriesPoint] = Field(default_factory=list)
    chart_data: dict[str, Any] = Field(default_factory=dict)


class BenchmarkExportResult(BaseModel):
    report: BenchmarkReport
    export_path: str
    bytes_written: int
    sha256: str


class MatePricing(BaseModel):
    provider_name: str | None = None
    model_name: str | None = None
    usd_per_1k_tokens: float | None = None
    pricing_catalog_url: str | None = None
    pricing_catalog_path: str | None = None
    currency: str = "USD"
    tokens_per_candidate: int = 1200
    manual_review_seconds_per_candidate: float = 18.0
    manual_retry_seconds_per_failed_source_attempt: float = 12.0


class MateRequest(BaseModel):
    pricing: MatePricing = Field(default_factory=MatePricing)


class PricingCatalogEntry(BaseModel):
    provider_name: str | None = None
    model_name: str | None = None
    usd_per_1k_tokens: float | None = None
    currency: str = "USD"
    notes: list[str] = Field(default_factory=list)


class PricingCatalogResponse(BaseModel):
    generated_at: datetime | None = None
    source_name: str | None = None
    source_url: str | None = None
    source_latency_ms: float | None = None
    entries: list[PricingCatalogEntry] = Field(default_factory=list)
    resolved_quote: PricingCatalogEntry | None = None
    resolved: bool = False


class MateReport(BaseModel):
    run_id: str
    objective: str
    output_profile: str
    experience_profile: str
    generated_at: datetime
    generation_latency_ms: float = 0.0
    raw_count: int = 0
    qualified_count: int = 0
    source_attempt_count: int = 0
    plugin_report_count: int = 0
    estimated_candidate_units_saved: int = 0
    estimated_time_saved_seconds: float = 0.0
    estimated_llm_calls_saved: float = 0.0
    estimated_tokens_saved: int = 0
    estimated_api_cost_saved: float | None = None
    pricing_applied: bool = False
    pricing_source_name: str | None = None
    pricing_source_url: str | None = None
    pricing_source_latency_ms: float | None = None
    assumptions: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    details: dict[str, Any] = Field(default_factory=dict)


class PilotRequest(BaseModel):
    run_id: str | None = None
    discovery: DiscoveryRequest | None = None
    mode: Literal["human", "agent", "hybrid"] = "human"
    max_suggestions: int = Field(default=5, ge=1, le=12)
    market: str | None = None
    industry: str | None = None
    objective: Objective | None = None


class PilotAdvice(BaseModel):
    source: Literal["run", "request"]
    run_id: str | None = None
    objective: Objective
    output_profile: OutputProfile
    experience_profile: ExperienceProfile
    topology: TopologyClass | None = None
    recommended_route: str | None = None
    clarification_mode: ClarificationMode = "rule"
    round_budget: int = 0
    needs_clarification: bool = False
    clarifying_questions: list[ClarificationQuestion] = Field(default_factory=list)
    replan_triggers: list[str] = Field(default_factory=list)
    stop_conditions: list[str] = Field(default_factory=list)
    generated_at: datetime
    generation_latency_ms: float = 0.0
    guidance_summary: str
    recommended_experience_profile: ExperienceProfile
    recommended_retrieval_mode: RetrievalMode
    recommended_enrichment_mode: EnrichmentMode
    recommended_output_profile: OutputProfile
    next_steps: list[str] = Field(default_factory=list)
    next_queries: list[str] = Field(default_factory=list)
    negative_terms: list[str] = Field(default_factory=list)
    preferred_domains: list[str] = Field(default_factory=list)
    mode_switches: list[str] = Field(default_factory=list)
    semantic_matches: list[dict[str, Any]] = Field(default_factory=list)
    human_prompt: str
    agent_prompt: str
    confidence: float = 0.0
    notes: list[str] = Field(default_factory=list)


class ProviderDescriptor(BaseModel):
    kind: RetrievalProviderKind
    name: str
    description: str
    supports_custom_endpoint: bool = True
    supports_site_domains: bool = False
    enabled_by_default: bool = True
    env_vars: list[str] = Field(default_factory=list)


class ProvidersResponse(BaseModel):
    items: list[ProviderDescriptor]
    total: int


class ProviderInterfaceDescriptor(BaseModel):
    family: ProviderFamily
    kind: str
    name: str
    description: str
    status: ProviderStatus = "available"
    supports_custom_endpoint: bool = True
    supports_health_check: bool = True
    supports_local_mode: bool = True
    enabled_by_default: bool = True
    env_vars: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ProviderCatalogResponse(BaseModel):
    items: list[ProviderInterfaceDescriptor]
    total: int


class LLMProviderDescriptor(BaseModel):
    name: str
    kind: Literal["omlx"]
    description: str
    default_model: str | None = None
    supports_custom_endpoint: bool = True
    supports_health_check: bool = True
    env_vars: list[str] = Field(default_factory=list)


class LLMProvidersResponse(BaseModel):
    items: list[LLMProviderDescriptor]
    total: int


class LLMHealthResponse(BaseModel):
    name: str
    available: bool
    base_url: str | None = None
    model_name: str | None = None
    latency_ms: float | None = None
    message: str | None = None
    checked_at: datetime


RetrievalPolicy.model_rebuild()


class AuditReport(BaseModel):
    run_id: str
    objective: str
    output_profile: str
    created_at: datetime | None = None
    entity_count: int = 0
    relation_count: int = 0
    telemetry_count: int = 0
    source_attempt_count: int = 0
    plugin_report_count: int = 0
    metrics: dict[str, float] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
    round_profiles: dict[str, int] = Field(default_factory=dict)
    provider_kinds: list[str] = Field(default_factory=list)
    source_classes: dict[str, int] = Field(default_factory=dict)


class AuditComparison(BaseModel):
    left_run_id: str
    right_run_id: str
    left: AuditReport
    right: AuditReport
    deltas: dict[str, float] = Field(default_factory=dict)
    winner: str | None = None


class JobCreateRequest(BaseModel):
    discovery: DiscoveryRequest
    wait_for_completion: bool = True


class JobRecord(BaseModel):
    job_id: str
    status: JobStatus
    objective: str
    output_profile: str
    project_id: str | None = None
    tenant_id: str | None = None
    created_at: datetime
    updated_at: datetime
    request: dict[str, Any]
    run_id: str | None = None
    error: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


class JobsResponse(BaseModel):
    items: list[JobRecord]
    total: int


class StreamEventRecord(BaseModel):
    job_id: str
    event_type: StreamEventType
    message: str
    created_at: datetime
    data: dict[str, Any] = Field(default_factory=dict)


class StreamEventsResponse(BaseModel):
    items: list[StreamEventRecord]
    total: int


class PluginReportRecord(BaseModel):
    plugin: EnrichmentPluginName
    target_entity_id: str
    status: str
    applied: bool = False
    message: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class PluginReportsResponse(BaseModel):
    items: list[PluginReportRecord]
    total: int


class PluginDescriptor(BaseModel):
    name: EnrichmentPluginName
    available: bool
    default_auto_enabled: bool
    execution_mode: str
    supported_entity_types: list[str] = Field(default_factory=list)
    notes: str | None = None


class PluginsResponse(BaseModel):
    items: list[PluginDescriptor]
    total: int
