from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from salva_core.schemas.enums import (
    ClarificationMode,
    EnrichmentMode,
    ExperienceProfile,
    Objective,
    OutputProfile,
    RetrievalMode,
    TopologyClass,
)
from salva_core.schemas.planner import ClarificationQuestion
from salva_core.schemas.request import DiscoveryRequest


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
