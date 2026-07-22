from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from salva_core.schemas.enums import (
    ClarificationMode,
    EnrichmentMode,
    ExperienceProfile,
    Objective,
    OutputProfile,
    RetrievalMode,
    TopologyClass,
)
from salva_core.schemas.request import DiscoveryIntent, DiscoveryRequest
from salva_core.schemas.topology import TopologyProbeResult, TopologyRoutePlan


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
