from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from salva_core.schemas.enums import JobStatus, StreamEventType
from salva_core.schemas.request import DiscoveryRequest


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
    heartbeat_at: datetime | None = None


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
