from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


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
