from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from salva_core.schemas import CanonicalEntity, CanonicalRelation, EvidenceRecord, HoldHyperedgeRecord, RunSnapshot


class HoldGraphNode(BaseModel):
    node_id: str
    node_type: str
    title: str
    summary: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class HoldGraphEdge(BaseModel):
    edge_id: str
    edge_type: str
    from_node_id: str
    to_node_id: str
    weight: float = 1.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class HoldGraphWalkResponse(BaseModel):
    run_id: str
    seed_entity_ids: list[str]
    depth: int
    generated_at: datetime
    total_nodes: int
    total_edges: int
    nodes: list[HoldGraphNode] = Field(default_factory=list)
    edges: list[HoldGraphEdge] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


def build_hold_graph_walk(
    snapshot: RunSnapshot,
    seed_entity_ids: list[str],
    depth: int = 1,
    include_evidence: bool = True,
    include_sources: bool = True,
) -> HoldGraphWalkResponse:
    if depth < 1:
        raise ValueError("depth must be at least 1")
    if not seed_entity_ids:
        raise ValueError("seed_entity_ids is required")

    entity_by_id = {entity.entity_id: entity for entity in snapshot.entities}
    relation_by_id = {relation.relation_id: relation for relation in snapshot.relations}
    evidence_by_id = {record.evidence_id: record for record in snapshot.evidence_records}
    hyperedge_by_id = {hyperedge.hyperedge_id: hyperedge for hyperedge in snapshot.hyperedges}

    nodes: dict[str, HoldGraphNode] = {}
    edges: dict[str, HoldGraphEdge] = {}
    frontier = [entity_id for entity_id in seed_entity_ids if entity_id in entity_by_id]
    visited_entities: set[str] = set(frontier)
    visited_relations: set[str] = set()
    visited_evidence: set[str] = set()
    visited_hyperedges: set[str] = set()
    visited_sources: set[str] = set()

    for entity_id in frontier:
        _ensure_entity_node(nodes, entity_by_id[entity_id])

    for _ in range(depth):
        next_frontier: list[str] = []
        current_frontier = list(frontier)

        for relation in snapshot.relations:
            if relation.relation_id in visited_relations:
                continue
            if relation.from_entity_id not in current_frontier and relation.to_entity_id not in current_frontier:
                continue
            visited_relations.add(relation.relation_id)
            _ensure_relation_node(nodes, relation)
            _add_edge(edges, relation.from_entity_id, relation.relation_id, "relation_out", relation.confidence, relation)
            _add_edge(edges, relation.relation_id, relation.to_entity_id, "relation_in", relation.confidence, relation)
            for entity_id in (relation.from_entity_id, relation.to_entity_id):
                if entity_id in entity_by_id and entity_id not in visited_entities:
                    visited_entities.add(entity_id)
                    next_frontier.append(entity_id)
                    _ensure_entity_node(nodes, entity_by_id[entity_id])
            for evidence_id in relation.evidence_ids:
                if evidence_id in evidence_by_id:
                    _link_evidence(
                        nodes,
                        edges,
                        relation.relation_id,
                        evidence_by_id[evidence_id],
                        include_sources=include_sources,
                        visited_evidence=visited_evidence,
                        visited_sources=visited_sources,
                    )

        if include_evidence:
            for entity_id in current_frontier:
                for record in snapshot.evidence_records:
                    if record.entity_id != entity_id or record.evidence_id in visited_evidence:
                        continue
                    _link_evidence(
                        nodes,
                        edges,
                        entity_id,
                        record,
                        include_sources=include_sources,
                        visited_evidence=visited_evidence,
                        visited_sources=visited_sources,
                    )

        for hyperedge in snapshot.hyperedges:
            if hyperedge.hyperedge_id in visited_hyperedges:
                continue
            member_ids = [member.member_id for member in hyperedge.members]
            if not any(member_id in current_frontier for member_id in member_ids):
                continue
            visited_hyperedges.add(hyperedge.hyperedge_id)
            _ensure_hyperedge_node(nodes, hyperedge)
            for member_id in member_ids:
                if member_id in entity_by_id:
                    _ensure_entity_node(nodes, entity_by_id[member_id])
                    _add_edge(edges, member_id, hyperedge.hyperedge_id, "hyperedge_member", 1.0, hyperedge)
                    _add_edge(edges, hyperedge.hyperedge_id, member_id, "hyperedge_contains", 1.0, hyperedge)
                    if member_id not in visited_entities:
                        visited_entities.add(member_id)
                        next_frontier.append(member_id)
            for evidence_id in hyperedge.evidence_ids:
                if evidence_id in evidence_by_id:
                    _link_evidence(
                        nodes,
                        edges,
                        hyperedge.hyperedge_id,
                        evidence_by_id[evidence_id],
                        include_sources=include_sources,
                        visited_evidence=visited_evidence,
                        visited_sources=visited_sources,
                    )

        frontier = [entity_id for entity_id in next_frontier if entity_id not in frontier]

    ordered_nodes = list(nodes.values())
    ordered_edges = list(edges.values())
    return HoldGraphWalkResponse(
        run_id=snapshot.run_id,
        seed_entity_ids=seed_entity_ids,
        depth=depth,
        generated_at=datetime.now(UTC),
        total_nodes=len(ordered_nodes),
        total_edges=len(ordered_edges),
        nodes=ordered_nodes,
        edges=ordered_edges,
        notes=[
            "Graph walk is read-only and derived from a run snapshot.",
            "Relations are expanded first, then evidence and hyperedges are attached.",
        ],
    )


def _ensure_entity_node(nodes: dict[str, HoldGraphNode], entity: CanonicalEntity) -> None:
    nodes.setdefault(
        entity.entity_id,
        HoldGraphNode(
            node_id=entity.entity_id,
            node_type="entity",
            title=entity.title,
            summary=entity.summary,
            metadata={
                "entity_type": entity.entity_type,
                "market": entity.market,
                "industry": entity.industry,
                "score": entity.score,
                "confidence": entity.confidence,
                "tags": entity.tags,
            },
        ),
    )


def _ensure_relation_node(nodes: dict[str, HoldGraphNode], relation: CanonicalRelation) -> None:
    nodes.setdefault(
        relation.relation_id,
        HoldGraphNode(
            node_id=relation.relation_id,
            node_type="relation",
            title=relation.relation_type,
            summary=f"{relation.from_entity_id} -> {relation.to_entity_id}",
            metadata={
                "relation_type": relation.relation_type,
                "confidence": relation.confidence,
                "evidence_ids": relation.evidence_ids,
            },
        ),
    )


def _ensure_hyperedge_node(nodes: dict[str, HoldGraphNode], hyperedge: HoldHyperedgeRecord) -> None:
    nodes.setdefault(
        hyperedge.hyperedge_id,
        HoldGraphNode(
            node_id=hyperedge.hyperedge_id,
            node_type="hyperedge",
            title=hyperedge.summary or hyperedge.hyperedge_type,
            summary=hyperedge.summary,
            metadata={
                "hyperedge_type": hyperedge.hyperedge_type,
                "confidence": hyperedge.confidence,
                "members": [member.model_dump(mode="json") for member in hyperedge.members],
                "evidence_ids": hyperedge.evidence_ids,
                "source_ids": hyperedge.source_ids,
            },
        ),
    )


def _ensure_evidence_node(nodes: dict[str, HoldGraphNode], record: EvidenceRecord) -> None:
    nodes.setdefault(
        record.evidence_id,
        HoldGraphNode(
            node_id=record.evidence_id,
            node_type="evidence",
            title=record.title or record.source_name or record.evidence_id,
            summary=record.snippet,
            metadata={
                "entity_id": record.entity_id,
                "source_url": record.source_url,
                "source_name": record.source_name,
                "captured_at": record.captured_at.isoformat() if record.captured_at else None,
            },
        ),
    )


def _ensure_source_node(nodes: dict[str, HoldGraphNode], source_url: str) -> str:
    source_id = f"source:{hashlib.sha1(source_url.encode('utf-8')).hexdigest()[:12]}"
    nodes.setdefault(
        source_id,
        HoldGraphNode(
            node_id=source_id,
            node_type="source",
            title=source_url,
            summary=source_url,
            metadata={"source_url": source_url},
        ),
    )
    return source_id


def _link_evidence(
    nodes: dict[str, HoldGraphNode],
    edges: dict[str, HoldGraphEdge],
    from_node_id: str,
    record: EvidenceRecord,
    include_sources: bool,
    visited_evidence: set[str],
    visited_sources: set[str],
) -> None:
    if record.evidence_id in visited_evidence:
        return
    visited_evidence.add(record.evidence_id)
    _ensure_evidence_node(nodes, record)
    _add_edge(edges, from_node_id, record.evidence_id, "supports", 1.0, record)
    if include_sources:
        source_id = _ensure_source_node(nodes, record.source_url)
        if source_id not in visited_sources:
            visited_sources.add(source_id)
        _add_edge(edges, record.evidence_id, source_id, "source_of", 1.0, record)


def _add_edge(
    edges: dict[str, HoldGraphEdge],
    from_node_id: str,
    to_node_id: str,
    edge_type: str,
    weight: float,
    payload: Any,
) -> None:
    edge_id = f"{from_node_id}:{edge_type}:{to_node_id}"
    if edge_id in edges:
        return
    edges[edge_id] = HoldGraphEdge(
        edge_id=edge_id,
        edge_type=edge_type,
        from_node_id=from_node_id,
        to_node_id=to_node_id,
        weight=weight,
        metadata=_payload_metadata(payload),
    )


def _payload_metadata(payload: Any) -> dict[str, Any]:
    if hasattr(payload, "model_dump"):
        return payload.model_dump(mode="json")
    if isinstance(payload, dict):
        return dict(payload)
    return {"payload": str(payload)}
