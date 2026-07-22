from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


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
