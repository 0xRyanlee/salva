from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class HoldFieldSpec(BaseModel):
    name: str
    type: str
    required: bool = False
    description: str
    examples: list[str] = Field(default_factory=list)


class HoldEntitySchema(BaseModel):
    entity_type: str
    description: str
    required_fields: list[HoldFieldSpec] = Field(default_factory=list)
    optional_fields: list[HoldFieldSpec] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class HoldRelationSchema(BaseModel):
    relation_type: str
    description: str
    from_entity_types: list[str] = Field(default_factory=list)
    to_entity_types: list[str] = Field(default_factory=list)
    required_fields: list[HoldFieldSpec] = Field(default_factory=list)
    optional_fields: list[HoldFieldSpec] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class HoldEntitySchemasResponse(BaseModel):
    items: list[HoldEntitySchema]
    total: int


class HoldRelationSchemasResponse(BaseModel):
    items: list[HoldRelationSchema]
    total: int


class HoldBoundaryRule(BaseModel):
    name: str
    description: str


class HoldCapability(BaseModel):
    name: str
    description: str
    mode: str


class HoldHyperedgeMember(BaseModel):
    entity_id: str
    role: str
    weight: float = 1.0
    evidence_ids: list[str] = Field(default_factory=list)


class HoldHyperedgeRecord(BaseModel):
    hyperedge_id: str
    hyperedge_type: str
    members: list[HoldHyperedgeMember] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    time_window_start: datetime | None = None
    time_window_end: datetime | None = None
    confidence: float = 0.0
    summary: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)


class HoldSchema(BaseModel):
    name: str = "hold"
    version: str = "0.1.0"
    storage_version: str = "0.1.0"
    migration_version: str = "0.1.0"
    migration_strategy: str = "append-only additive migrations"
    status: str = "draft"
    description: str = (
        "Logical hypergraph container for Salva. Keeps facts, evidence, relations, "
        "hyperedges, and projection boundaries separate."
    )
    boundary_rules: list[HoldBoundaryRule] = Field(default_factory=list)
    capabilities: list[HoldCapability] = Field(default_factory=list)
    entity_types: list[str] = Field(default_factory=list)
    relation_types: list[str] = Field(default_factory=list)
    hyperedge_types: list[str] = Field(default_factory=list)
    entity_schemas: list[HoldEntitySchema] = Field(default_factory=list)
    relation_schemas: list[HoldRelationSchema] = Field(default_factory=list)
    projection_modes: list[str] = Field(default_factory=list)
    storage_planes: list[str] = Field(default_factory=list)
    event_planes: list[str] = Field(default_factory=list)
    migration_notes: list[str] = Field(default_factory=list)


def build_hold_entity_schemas() -> list[HoldEntitySchema]:
    shared_required = [
        HoldFieldSpec(
            name="entity_id",
            type="string",
            required=True,
            description="Stable canonical identifier for the entity.",
            examples=["lead:acme-de-001", "company:acme-corp"],
        ),
        HoldFieldSpec(
            name="entity_type",
            type="string",
            required=True,
            description="Canonical entity type used by Hold.",
            examples=["lead", "company", "event"],
        ),
        HoldFieldSpec(
            name="title",
            type="string",
            required=True,
            description="Human-readable canonical name or title.",
            examples=["Acme Software GmbH", "Berlin Tech Summit 2026"],
        ),
    ]
    shared_optional = [
        HoldFieldSpec(
            name="summary",
            type="string",
            description="Short, readable summary.",
            examples=["Software reseller in Germany with DACH region focus."],
        ),
        HoldFieldSpec(
            name="market",
            type="string",
            description="Target market or region.",
            examples=["Germany", "Taiwan"],
        ),
        HoldFieldSpec(
            name="industry",
            type="string",
            description="Target industry or vertical.",
            examples=["software", "education"],
        ),
        HoldFieldSpec(
            name="tags",
            type="array[string]",
            description="Derived or user-facing labels.",
            examples=["distributor", "B2B", "trade-show"],
        ),
        HoldFieldSpec(
            name="source_urls",
            type="array[string]",
            description="Source URLs that support the entity.",
            examples=["https://example.com/profile"],
        ),
        HoldFieldSpec(
            name="evidence",
            type="array[object]",
            description="Evidence items supporting the entity.",
            examples=["[{source_url, title, snippet}]"],
        ),
        HoldFieldSpec(
            name="confidence",
            type="number",
            description="Confidence in the canonicalization / extraction result.",
            examples=["0.87"],
        ),
        HoldFieldSpec(
            name="score",
            type="number",
            description="Ranking or qualification score.",
            examples=["0.91"],
        ),
        HoldFieldSpec(
            name="status",
            type="string",
            description="Lifecycle status for downstream workflows.",
            examples=["new", "qualified", "reviewed"],
        ),
        HoldFieldSpec(
            name="attributes",
            type="object",
            description="Type-specific extension payload kept for compatibility.",
            examples=["{\"organizer_email\": \"hello@example.com\"}"],
        ),
    ]
    event_optional = [
        HoldFieldSpec(
            name="event",
            type="object",
            description="Event-specific payload kept in a dedicated submodel so shared entity fields remain compact.",
            examples=["{\"starts_at\": \"2026-05-01T09:00:00+08:00\", \"city\": \"Taipei\"}"],
        ),
    ]

    return [
        HoldEntitySchema(
            entity_type="lead",
            description="Prospect, distributor, buyer, or contact-worthy business lead.",
            required_fields=shared_required,
            optional_fields=shared_optional,
            notes=[
                "Lead entities typically expose contact and qualification attributes in the extension payload.",
            ],
        ),
        HoldEntitySchema(
            entity_type="company",
            description="Company or organization profile.",
            required_fields=shared_required,
            optional_fields=shared_optional,
            notes=["Company entities should preserve market and industry normalization."],
        ),
        HoldEntitySchema(
            entity_type="event",
            description="Event, meetup, conference, exhibition, or webinar record.",
            required_fields=shared_required,
            optional_fields=[*shared_optional, *event_optional],
            notes=["Event entities should keep time, venue, organizer, and speaker details in the dedicated event submodel."],
        ),
        HoldEntitySchema(
            entity_type="activity_signal",
            description="Weak market, collaboration, or intent signal extracted from sources.",
            required_fields=shared_required,
            optional_fields=shared_optional,
            notes=["Signals should remain evidence-backed and low-friction to downgrade or merge."],
        ),
        HoldEntitySchema(
            entity_type="document",
            description="Document, article, landing page, or other source-bearing record.",
            required_fields=shared_required,
            optional_fields=shared_optional,
            notes=["Documents should preserve retrieval provenance and snippet-level evidence."],
        ),
        HoldEntitySchema(
            entity_type="source",
            description="Originating source surface such as a website, feed, or provider endpoint.",
            required_fields=shared_required,
            optional_fields=shared_optional,
            notes=["Source entities are used to anchor provenance and source reliability."],
        ),
        HoldEntitySchema(
            entity_type="person",
            description="Named person, speaker, operator, contact, or identity-bearing record.",
            required_fields=shared_required,
            optional_fields=shared_optional,
            notes=["Person entities should preserve role, organization, and contact relationships in attributes."],
        ),
    ]


def build_hold_relation_schemas() -> list[HoldRelationSchema]:
    relation_fields = [
        HoldFieldSpec(
            name="relation_id",
            type="string",
            required=True,
            description="Stable identifier for the relation.",
            examples=["rel:lead-company-001"],
        ),
        HoldFieldSpec(
            name="schema_name",
            type="string",
            required=True,
            description="Versioned canonical relation schema family name.",
            examples=["canonical_relation"],
        ),
        HoldFieldSpec(
            name="schema_version",
            type="string",
            required=True,
            description="Contract version for the canonical relation schema.",
            examples=["0.1.0"],
        ),
        HoldFieldSpec(
            name="storage_version",
            type="string",
            required=True,
            description="Physical storage version for the persisted relation row.",
            examples=["0.1.0"],
        ),
        HoldFieldSpec(
            name="migration_version",
            type="string",
            required=True,
            description="Migration registry version for the persisted relation row.",
            examples=["0.1.0"],
        ),
        HoldFieldSpec(
            name="relation_type",
            type="string",
            required=True,
            description="Canonical relation type.",
            examples=["related_to", "evidence_for"],
        ),
        HoldFieldSpec(
            name="from_entity_id",
            type="string",
            required=True,
            description="Source entity identifier.",
            examples=["lead:acme-de-001"],
        ),
        HoldFieldSpec(
            name="to_entity_id",
            type="string",
            required=True,
            description="Target entity identifier.",
            examples=["company:acme-corp"],
        ),
        HoldFieldSpec(
            name="confidence",
            type="number",
            required=True,
            description="Confidence score for the relation.",
            examples=["0.82"],
        ),
        HoldFieldSpec(
            name="evidence_ids",
            type="array[string]",
            description="Evidence records backing the relation.",
            examples=["[\"evidence:123\"]"],
        ),
        HoldFieldSpec(
            name="attributes",
            type="object",
            description="Relation-specific metadata.",
            examples=["{\"role\": \"distributor\"}"],
        ),
    ]

    broad_entities = [
        "lead",
        "company",
        "event",
        "activity_signal",
        "document",
        "source",
        "person",
    ]
    return [
        HoldRelationSchema(
            relation_type="related_to",
            description="Generic canonical relation used as a safe default. Versioned relation rows keep contract, storage, and migration metadata.",
            from_entity_types=broad_entities,
            to_entity_types=broad_entities,
            required_fields=relation_fields,
            notes=["Use when no more specific typed relation applies."],
        ),
        HoldRelationSchema(
            relation_type="organized_by",
            description="Event is organized by a company, person, or source.",
            from_entity_types=["event"],
            to_entity_types=["company", "person", "source"],
            required_fields=relation_fields,
        ),
        HoldRelationSchema(
            relation_type="hosted_by",
            description="Event or content is hosted by a company or source.",
            from_entity_types=["event", "document"],
            to_entity_types=["company", "source"],
            required_fields=relation_fields,
        ),
        HoldRelationSchema(
            relation_type="occurs_in",
            description="Event occurs in a place or is scoped to a source surface.",
            from_entity_types=["event"],
            to_entity_types=["document", "source", "company"],
            required_fields=relation_fields,
        ),
        HoldRelationSchema(
            relation_type="belongs_to_market",
            description="Entity is associated with a market or market-facing context.",
            from_entity_types=broad_entities,
            to_entity_types=["company", "source", "document"],
            required_fields=relation_fields,
        ),
        HoldRelationSchema(
            relation_type="has_contact",
            description="Entity exposes a contact person or contact surface.",
            from_entity_types=["company", "lead", "source", "document"],
            to_entity_types=["person", "lead"],
            required_fields=relation_fields,
        ),
        HoldRelationSchema(
            relation_type="derived_from",
            description="Canonical record is derived from a document or source.",
            from_entity_types=broad_entities,
            to_entity_types=["document", "source"],
            required_fields=relation_fields,
        ),
        HoldRelationSchema(
            relation_type="evidence_for",
            description="Evidence record or source supports an entity or relation.",
            from_entity_types=["document", "source"],
            to_entity_types=broad_entities,
            required_fields=relation_fields,
        ),
        HoldRelationSchema(
            relation_type="entity_to_entity",
            description="Compatibility alias for a generic entity-to-entity relation.",
            from_entity_types=broad_entities,
            to_entity_types=broad_entities,
            required_fields=relation_fields,
            notes=["Used as a migration bridge from legacy schemas.", "Relation rows are versioned so legacy imports can be compared against canonical contracts."],
        ),
        HoldRelationSchema(
            relation_type="entity_to_evidence",
            description="Compatibility alias for entity-to-evidence linkage.",
            from_entity_types=broad_entities,
            to_entity_types=["document", "source"],
            required_fields=relation_fields,
            notes=["Used as a migration bridge from legacy schemas.", "Relation rows are versioned so legacy imports can be compared against canonical contracts."],
        ),
        HoldRelationSchema(
            relation_type="entity_to_hyperedge",
            description="Compatibility alias for entity membership in a hyperedge.",
            from_entity_types=broad_entities,
            to_entity_types=["event", "activity_signal", "document", "source"],
            required_fields=relation_fields,
            notes=["Used as a migration bridge from legacy schemas.", "Relation rows are versioned so legacy imports can be compared against canonical contracts."],
        ),
        HoldRelationSchema(
            relation_type="event_membership",
            description="Compatibility relation for event membership.",
            from_entity_types=["lead", "company", "person", "source"],
            to_entity_types=["event"],
            required_fields=relation_fields,
        ),
        HoldRelationSchema(
            relation_type="signal_membership",
            description="Compatibility relation for signal membership.",
            from_entity_types=broad_entities,
            to_entity_types=["activity_signal"],
            required_fields=relation_fields,
        ),
    ]


def build_hold_schema() -> HoldSchema:
    return HoldSchema(
        boundary_rules=[
            HoldBoundaryRule(
                name="fact-first",
                description="Hold preserves canonical facts and evidence before projections.",
            ),
            HoldBoundaryRule(
                name="projection-only",
                description="Readable views are projections and must not overwrite facts.",
            ),
            HoldBoundaryRule(
                name="evidence-backed",
                description="Every hyperedge should retain evidence and source lineage.",
            ),
            HoldBoundaryRule(
                name="backend-agnostic",
                description="Logical contract stays stable even when the storage backend changes.",
            ),
            HoldBoundaryRule(
                name="versioned-storage",
                description="Schema and migration state are recorded explicitly and can be queried.",
            ),
        ],
        capabilities=[
            HoldCapability(
                name="event_hyperedge",
                description="Bundle multi-party events with evidence and time windows.",
                mode="event-first",
            ),
            HoldCapability(
                name="signal_hyperedge",
                description="Bundle weak signals across multiple sources into one semantic unit.",
                mode="signal-first",
            ),
            HoldCapability(
                name="query_family_hyperedge",
                description="Capture successful query families and their source clusters.",
                mode="query-first",
            ),
            HoldCapability(
                name="entity_projection",
                description="Expose entity-centered views without mutating the underlying facts.",
                mode="projection",
            ),
        ],
        entity_types=[
            "lead",
            "company",
            "event",
            "activity_signal",
            "document",
            "source",
        ],
        relation_types=[
            "related_to",
            "organized_by",
            "hosted_by",
            "occurs_in",
            "belongs_to_market",
            "has_contact",
            "derived_from",
            "evidence_for",
            "entity_to_entity",
            "entity_to_evidence",
            "entity_to_hyperedge",
            "event_membership",
            "signal_membership",
        ],
        entity_schemas=build_hold_entity_schemas(),
        relation_schemas=build_hold_relation_schemas(),
        hyperedge_types=[
            "event_hyperedge",
            "signal_hyperedge",
            "partnership_hyperedge",
            "query_family_hyperedge",
        ],
        projection_modes=[
            "entity_view",
            "query_view",
            "hyperedge_view",
            "audit_view",
        ],
        storage_planes=[
            "state",
            "structured",
            "semantic",
            "raw_evidence",
        ],
        event_planes=[
            "run",
            "job",
            "telemetry",
            "evidence",
            "query_family",
        ],
        migration_notes=[
            "Current storage updates are additive and append-only by default.",
            "Version registry is stored alongside the canonical runtime data.",
            "Backward-incompatible changes should introduce a new schema version.",
        ],
    )
