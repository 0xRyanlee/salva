from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class CampaignRecord(BaseModel):
    campaign_id: str
    name: str
    description: str | None = None
    status: Literal["active", "archived"] = "active"
    retention_days: int | None = None
    purge_at: datetime | None = None
    cache_cleared_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None = None
    run_count: int = 0
    memory_quarantine_count: int = 0
    memory_promoted_count: int = 0


class CampaignsResponse(BaseModel):
    items: list[CampaignRecord]
    total: int


class CampaignCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None


class CampaignUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None


class CampaignArchiveRequest(BaseModel):
    retention_days: int | None = None


class CampaignDeleteResponse(BaseModel):
    campaign_id: str
    deleted: dict[str, int]


class CampaignCacheClearResponse(BaseModel):
    campaign_id: str
    cleared: dict[str, int]
    cache_cleared_at: datetime
