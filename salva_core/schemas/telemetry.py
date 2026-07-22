from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


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


class TelemetryResponse(BaseModel):
    items: list[TelemetryRecord]
    total: int


class FeedbackRecord(BaseModel):
    entity_id: str
    feedback_type: Literal["accept", "partial_accept", "reject", "contacted", "converted"]
    note: str | None = None
    created_at: datetime | None = None


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
