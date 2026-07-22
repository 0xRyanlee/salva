from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from salva_core.schemas.enums import (
    CacheMode,
    EnrichmentMode,
    EnrichmentPluginName,
    MemoryReadScope,
    MemoryWriteMode,
    Objective,
    OutputProfile,
    PersistenceMode,
    RetrievalMode,
    RetrievalProviderKind,
)


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
