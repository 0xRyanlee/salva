from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


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
