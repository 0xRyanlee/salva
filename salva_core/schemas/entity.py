from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from salva_core.schemas.enums import EntityType
from salva_core.schemas.evidence import EvidenceItem


class EventDetails(BaseModel):
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    timezone: str | None = None
    location_name: str | None = None
    location_address: str | None = None
    city: str | None = None
    country: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    organizer_name: str | None = None
    organizer_email: str | None = None
    organizer_domain: str | None = None
    capacity: int | None = None
    price_amount: float | None = None
    currency: str | None = None
    cover_image_url: str | None = None
    speaker_names: list[str] = Field(default_factory=list)
    venue_name: str | None = None


class CanonicalEntity(BaseModel):
    entity_id: str
    entity_type: EntityType
    title: str
    summary: str | None = None
    market: str | None = None
    industry: str | None = None
    tags: list[str] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    confidence: float = 0.0
    score: float = 0.0
    status: str = "new"
    event: EventDetails | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
