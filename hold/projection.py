from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from salva_core.schemas import CanonicalEntity, RunSnapshot

from .schema import HoldSchema, build_hold_schema


class HoldViewDescriptor(BaseModel):
    name: str
    description: str
    mode: str
    source_planes: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class HoldProjectionItem(BaseModel):
    item_id: str
    item_type: str
    title: str
    summary: str | None = None
    score: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class HoldProjectionResponse(BaseModel):
    run_id: str
    view_name: str
    generated_at: datetime
    total: int
    items: list[HoldProjectionItem] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class HoldViewsResponse(BaseModel):
    items: list[HoldViewDescriptor] = Field(default_factory=list)
    total: int = 0


def build_hold_views(schema: HoldSchema | None = None) -> HoldViewsResponse:
    _schema = schema or build_hold_schema()
    items = [
        HoldViewDescriptor(
            name="entity_view",
            description="Entity-centered projection for callers that want canonical records.",
            mode="projection",
            source_planes=["structured", "raw_evidence"],
            notes=["Stable by default", "Best for downstream transforms"],
        ),
        HoldViewDescriptor(
            name="query_view",
            description="Query-family projection for retrieval feedback and routing.",
            mode="query-first",
            source_planes=["semantic", "telemetry"],
            notes=["Useful for pilot / routing / optimization"],
        ),
        HoldViewDescriptor(
            name="hyperedge_view",
            description="Hyperedge projection for typed multi-member relations.",
            mode="hypergraph",
            source_planes=["structured", "semantic", "raw_evidence"],
            notes=["Shows multi-member relations with roles and evidence lineage"],
        ),
        HoldViewDescriptor(
            name="audit_view",
            description="Audit-centered projection for evidence, telemetry, and source lineage.",
            mode="audit",
            source_planes=["raw_evidence", "state"],
            notes=["Useful for review and export"],
        ),
    ]
    return HoldViewsResponse(items=items, total=len(items))


def project_hold_view(snapshot: RunSnapshot, view_name: str) -> HoldProjectionResponse:
    generated_at = datetime.now(UTC)

    if view_name == "entity_view":
        items = [_entity_item(entity) for entity in snapshot.entities]
        notes = ["Entity-centered projection built from canonical entities."]
    elif view_name == "query_view":
        items = [
            HoldProjectionItem(
                item_id=record.memory_id,
                item_type="query_family",
                title=record.query,
                summary=f"strategy={record.strategy}, round={record.round_num}",
                score=record.success_score,
                metadata={
                    "objective": record.objective,
                    "output_profile": record.output_profile,
                    "query_signature": record.query_signature,
                    "raw_total": record.raw_total,
                    "qualified_total": record.qualified_total,
                    "avg_score": record.avg_score,
                    "source_nodes": record.source_nodes,
                },
            )
            for record in snapshot.query_family_memory
        ]
        notes = ["Query-family projection built from semantic memory."]
    elif view_name == "hyperedge_view":
        items = [
            HoldProjectionItem(
                item_id=hyperedge.hyperedge_id,
                item_type=hyperedge.hyperedge_type,
                title=hyperedge.summary or hyperedge.hyperedge_type,
                summary=hyperedge.summary,
                score=hyperedge.confidence,
                metadata={
                    "run_id": hyperedge.run_id,
                    "members": [member.model_dump(mode="json") for member in hyperedge.members],
                    "evidence_ids": hyperedge.evidence_ids,
                    "source_ids": hyperedge.source_ids,
                    "properties": hyperedge.properties,
                    "created_at": hyperedge.created_at.isoformat() if hyperedge.created_at else None,
                },
            )
            for hyperedge in snapshot.hyperedges
        ]
        notes = ["Hyperedge projection built from typed multi-member relations."]
    elif view_name == "audit_view":
        items = [
            HoldProjectionItem(
                item_id=snapshot.run_id,
                item_type="audit",
                title=snapshot.objective,
                summary=f"entities={snapshot.entity_count}, relations={snapshot.relation_count}, evidence={snapshot.evidence_count}",
                score=float(snapshot.audit.metrics.get("qualified_rate", 0.0)) if snapshot.audit else 0.0,
                metadata={
                    "output_profile": snapshot.output_profile,
                    "telemetry_count": snapshot.telemetry_count,
                    "source_attempt_count": snapshot.source_attempt_count,
                    "plugin_report_count": snapshot.plugin_report_count,
                    "metrics": snapshot.audit.metrics if snapshot.audit else {},
                },
            )
        ]
        notes = ["Audit projection built from run snapshot metadata."]
    else:
        raise ValueError(f"unsupported hold view: {view_name}")

    return HoldProjectionResponse(
        run_id=snapshot.run_id,
        view_name=view_name,
        generated_at=generated_at,
        total=len(items),
        items=items,
        notes=notes,
    )


def _entity_item(entity: CanonicalEntity) -> HoldProjectionItem:
    return HoldProjectionItem(
        item_id=entity.entity_id,
        item_type=entity.entity_type,
        title=entity.title,
        summary=entity.summary,
        score=entity.score,
        metadata={
            "market": entity.market,
            "industry": entity.industry,
            "confidence": entity.confidence,
            "status": entity.status,
            "tags": entity.tags,
            "source_urls": entity.source_urls,
            "evidence_count": len(entity.evidence),
        },
    )
