from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from salva_core.schemas.enums import RelationType


class CanonicalRelation(BaseModel):
    relation_id: str
    schema_name: str = "canonical_relation"
    schema_version: str = "0.1.0"
    storage_version: str = "0.1.0"
    migration_version: str = "0.1.0"
    relation_type: RelationType
    from_entity_id: str
    to_entity_id: str
    confidence: float = 0.0
    evidence_ids: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)


class RelationRecord(BaseModel):
    relation_id: str
    run_id: str
    schema_name: str = "canonical_relation"
    schema_version: str = "0.1.0"
    storage_version: str = "0.1.0"
    migration_version: str = "0.1.0"
    relation_type: RelationType
    from_entity_id: str
    to_entity_id: str
    confidence: float = 0.0
    evidence_ids: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None


class RelationsResponse(BaseModel):
    items: list[RelationRecord]
    total: int


class RelationQueryRequest(BaseModel):
    run_id: str | None = None
    relation_type: RelationType | None = None
    from_entity_id: str | None = None
    to_entity_id: str | None = None
    limit: int = Field(default=200, ge=1, le=500)
    offset: int = Field(default=0, ge=0)
