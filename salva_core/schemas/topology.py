from __future__ import annotations

from pydantic import BaseModel, Field

from salva_core.schemas.enums import (
    EnrichmentMode,
    ExperienceProfile,
    Objective,
    OutputProfile,
    RetrievalHealth,
    RetrievalMode,
    TopologyClass,
)
from salva_core.schemas.request import DiscoveryRequest


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


class RouteCatalogResponse(BaseModel):
    items: list[RouteCatalogEntry] = Field(default_factory=list)
    total: int = 0
    source_dir: str | None = None
