from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from salva_core.schemas.audit import AuditReport
from salva_core.schemas.entity import CanonicalEntity
from salva_core.schemas.enums import Objective, OutputProfile
from salva_core.schemas.evidence import EvidenceChainRecord, EvidenceRecord, HoldHyperedgeRecord
from salva_core.schemas.memory import QueryFamilyMemoryRecord
from salva_core.schemas.plugin import PluginReportRecord
from salva_core.schemas.relation import CanonicalRelation
from salva_core.schemas.telemetry import SourceAttemptRecord, TelemetryRecord


class DiscoveryResponse(BaseModel):
    objective: Objective
    output_profile: OutputProfile
    entities: list[CanonicalEntity]
    transformed_items: list[dict[str, Any]] = Field(default_factory=list)
    relations: list[CanonicalRelation] = Field(default_factory=list)
    telemetry: list[TelemetryRecord] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


class RunRecord(BaseModel):
    run_id: str
    objective: str
    output_profile: str
    created_at: datetime
    request: dict[str, Any]
    meta: dict[str, Any]
    project_id: str | None = None
    campaign_id: str | None = None
    continuation_id: str | None = None
    entity_count: int = 0
    relation_count: int = 0


class RunsResponse(BaseModel):
    items: list[RunRecord]
    total: int


class RunSnapshot(BaseModel):
    run_id: str
    objective: str
    output_profile: str
    created_at: datetime | None = None
    generated_at: datetime
    request: dict[str, Any]
    meta: dict[str, Any] = Field(default_factory=dict)
    entities: list[CanonicalEntity] = Field(default_factory=list)
    relations: list[CanonicalRelation] = Field(default_factory=list)
    evidence_records: list[EvidenceRecord] = Field(default_factory=list)
    evidence_chains: list[EvidenceChainRecord] = Field(default_factory=list)
    hyperedges: list[HoldHyperedgeRecord] = Field(default_factory=list)
    query_family_memory: list[QueryFamilyMemoryRecord] = Field(default_factory=list)
    telemetry: list[TelemetryRecord] = Field(default_factory=list)
    source_attempts: list[SourceAttemptRecord] = Field(default_factory=list)
    plugin_reports: list[PluginReportRecord] = Field(default_factory=list)
    audit: AuditReport | None = None
    entity_count: int = 0
    relation_count: int = 0
    evidence_count: int = 0
    evidence_chain_count: int = 0
    hyperedge_count: int = 0
    query_family_count: int = 0
    telemetry_count: int = 0
    source_attempt_count: int = 0
    plugin_report_count: int = 0


class SnapshotExportRequest(BaseModel):
    output_path: str | None = None


class SnapshotExportResult(BaseModel):
    snapshot: RunSnapshot
    export_path: str
    bytes_written: int
    sha256: str
