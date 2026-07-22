from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


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
