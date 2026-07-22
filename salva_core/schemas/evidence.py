from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    source_url: str
    source_name: str | None = None
    title: str | None = None
    snippet: str | None = None
    captured_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidenceRecord(BaseModel):
    evidence_id: str
    run_id: str
    entity_id: str
    source_url: str
    source_name: str | None = None
    title: str | None = None
    snippet: str | None = None
    captured_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidenceChainLink(BaseModel):
    evidence_id: str
    source_url: str
    source_name: str | None = None
    title: str | None = None
    snippet: str | None = None
    captured_at: datetime | None = None
    relation_ids: list[str] = Field(default_factory=list)
    hyperedge_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidenceChainRecord(BaseModel):
    entity_id: str
    entity_title: str | None = None
    run_id: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    relation_ids: list[str] = Field(default_factory=list)
    hyperedge_ids: list[str] = Field(default_factory=list)
    links: list[EvidenceChainLink] = Field(default_factory=list)
    first_captured_at: datetime | None = None
    last_captured_at: datetime | None = None
    evidence_count: int = 0
    relation_count: int = 0
    hyperedge_count: int = 0
    notes: list[str] = Field(default_factory=list)


class HoldHyperedgeMember(BaseModel):
    member_id: str
    member_kind: str
    role: str
    weight: float = 1.0
    evidence_ids: list[str] = Field(default_factory=list)


class HoldHyperedgeRecord(BaseModel):
    hyperedge_id: str
    run_id: str
    hyperedge_type: str
    summary: str | None = None
    confidence: float = 0.0
    members: list[HoldHyperedgeMember] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None


class EvidenceResponse(BaseModel):
    items: list[EvidenceRecord]
    total: int


class EvidenceChainsRequest(BaseModel):
    run_id: str | None = None
    entity_id: str | None = None
    limit: int = Field(default=200, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class EvidenceChainsResponse(BaseModel):
    items: list[EvidenceChainRecord]
    total: int


class HyperedgesResponse(BaseModel):
    items: list[HoldHyperedgeRecord]
    total: int


class HoldMigrationRecord(BaseModel):
    registry_id: str
    schema_name: str
    hold_version: str
    storage_version: str
    migration_version: str
    migration_strategy: str
    status: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class HoldMigrationsResponse(BaseModel):
    items: list[HoldMigrationRecord]
    total: int
