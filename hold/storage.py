from __future__ import annotations

from pydantic import BaseModel, Field

from .schema import HoldSchema, build_hold_schema


class HoldStorageTable(BaseModel):
    name: str
    plane: str
    purpose: str
    primary_key: str
    indexed_columns: list[str] = Field(default_factory=list)
    foreign_keys: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class HoldStorageIndex(BaseModel):
    name: str
    table: str
    columns: list[str] = Field(default_factory=list)
    kind: str = "btree"
    purpose: str
    notes: list[str] = Field(default_factory=list)


class HoldStoragePlane(BaseModel):
    name: str
    mode: str
    description: str
    tables: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class HoldStorageCatalog(BaseModel):
    name: str = "hold"
    version: str = "0.1.0"
    storage_version: str = "0.1.0"
    migration_version: str = "0.1.0"
    status: str = "draft"
    backend: str = "sqlite"
    description: str = (
        "Logical storage and index catalog for the Hold container. "
        "It documents physical tables, index surfaces, and logical planes."
    )
    hold_schema: HoldSchema = Field(default_factory=build_hold_schema)
    planes: list[HoldStoragePlane] = Field(default_factory=list)
    tables: list[HoldStorageTable] = Field(default_factory=list)
    indexes: list[HoldStorageIndex] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


def build_hold_storage_catalog() -> HoldStorageCatalog:
    planes = [
        HoldStoragePlane(
            name="state",
            mode="sqlite",
            description="Operational state and control-plane tables.",
            tables=["discovery_runs", "jobs", "stream_events", "hold_schema_registry"],
            notes=["Append-only first, with explicit migration registry."],
        ),
        HoldStoragePlane(
            name="structured",
            mode="sqlite",
            description="Structured runtime facts, traces, and derived records.",
            tables=[
                "telemetry_records",
                "source_attempts",
                "plugin_reports",
                "evidence_records",
                "hyperedges",
                "query_family_memory",
            ],
            notes=["These tables are the main runtime fact surface."],
        ),
        HoldStoragePlane(
            name="semantic",
            mode="logical",
            description="Semantic memory and similarity-ready materializations.",
            tables=["query_family_memory", "semantic_vectors", "hyperedges"],
            notes=["Can later be projected to vector or graph backends."],
        ),
        HoldStoragePlane(
            name="raw_evidence",
            mode="sqlite",
            description="Preserves raw evidence, event streams, and source lineage.",
            tables=["evidence_records", "evidence_chain_records", "stream_events", "source_attempts"],
            notes=["Used for audits, replay, and provenance checks."],
        ),
    ]

    tables = [
        HoldStorageTable(
            name="discovery_runs",
            plane="state",
            purpose="Persist canonical run requests, entities, relations, and meta.",
            primary_key="run_id",
            indexed_columns=["created_at"],
            notes=["Main run history record."],
        ),
        HoldStorageTable(
            name="telemetry_records",
            plane="structured",
            purpose="Persist per-round retrieval telemetry and feedback signals.",
            primary_key="telemetry_id",
            indexed_columns=["run_id", "query"],
            foreign_keys=["run_id -> discovery_runs.run_id"],
        ),
        HoldStorageTable(
            name="source_attempts",
            plane="raw_evidence",
            purpose="Persist provider attempts, fallback usage, and crawl outcomes.",
            primary_key="attempt_id",
            indexed_columns=["run_id", "strategy"],
            foreign_keys=["run_id -> discovery_runs.run_id"],
        ),
        HoldStorageTable(
            name="jobs",
            plane="state",
            purpose="Persist queued and completed voyage records.",
            primary_key="job_id",
            indexed_columns=["status", "created_at"],
            notes=["Supports worker handoff and SSE/event inspection."],
        ),
        HoldStorageTable(
            name="stream_events",
            plane="raw_evidence",
            purpose="Persist append-only event logs for jobs.",
            primary_key="event_id",
            indexed_columns=["job_id"],
            foreign_keys=["job_id -> jobs.job_id"],
        ),
        HoldStorageTable(
            name="plugin_reports",
            plane="structured",
            purpose="Persist enrichment plugin outcomes and messages.",
            primary_key="report_id",
            indexed_columns=["run_id", "plugin"],
            foreign_keys=["run_id -> discovery_runs.run_id"],
        ),
        HoldStorageTable(
            name="evidence_records",
            plane="raw_evidence",
            purpose="Persist extracted evidence per entity and source.",
            primary_key="evidence_id",
            indexed_columns=["run_id", "entity_id"],
            foreign_keys=["run_id -> discovery_runs.run_id"],
        ),
        HoldStorageTable(
            name="evidence_chain_records",
            plane="raw_evidence",
            purpose="Persist entity-grouped evidence chains with relation and hyperedge lineage.",
            primary_key="chain_id",
            indexed_columns=["run_id", "entity_id"],
            foreign_keys=["run_id -> discovery_runs.run_id"],
            notes=["This is the materialized chain view used by audit and graph-style retrieval."],
        ),
        HoldStorageTable(
            name="relation_records",
            plane="structured",
            purpose="Persist versioned typed binary relations between canonical entities.",
            primary_key="relation_id",
            indexed_columns=["run_id", "schema_name", "schema_version", "relation_type", "from_entity_id", "to_entity_id"],
            foreign_keys=["run_id -> discovery_runs.run_id"],
            notes=["Relation-aware retrieval should query this plane before graph backends are added.", "Relation rows carry schema and migration metadata so the contract can evolve without breaking callers."],
        ),
        HoldStorageTable(
            name="hyperedges",
            plane="structured",
            purpose="Persist typed multi-member hyperedges and lineage.",
            primary_key="hyperedge_id",
            indexed_columns=["run_id", "hyperedge_type"],
            foreign_keys=["run_id -> discovery_runs.run_id"],
        ),
        HoldStorageTable(
            name="hold_schema_registry",
            plane="state",
            purpose="Persist the versioned Hold schema and migration registry.",
            primary_key="registry_id",
            indexed_columns=["schema_name", "hold_version", "storage_version", "migration_version"],
            notes=["Used to expose the exact contract version callers should target."],
        ),
        HoldStorageTable(
            name="query_family_memory",
            plane="semantic",
            purpose="Persist successful query-family clusters and optimization memory.",
            primary_key="memory_id",
            indexed_columns=["run_id", "objective", "strategy", "query_signature"],
            foreign_keys=["run_id -> discovery_runs.run_id"],
        ),
        HoldStorageTable(
            name="semantic_vectors",
            plane="semantic",
            purpose="Persist vector representations for query-family semantic retrieval.",
            primary_key="vector_id",
            indexed_columns=["vector_kind", "run_id", "objective", "strategy", "source_id"],
            foreign_keys=["source_id -> query_family_memory.memory_id", "run_id -> discovery_runs.run_id"],
            notes=["This is the local vector plane used for semantic search."],
        ),
    ]

    indexes = [
        HoldStorageIndex(
            name="idx_telemetry_run_id",
            table="telemetry_records",
            columns=["run_id"],
            purpose="Find telemetry by run quickly.",
        ),
        HoldStorageIndex(
            name="idx_telemetry_query",
            table="telemetry_records",
            columns=["query"],
            purpose="Support query-family inspection and audit lookups.",
        ),
        HoldStorageIndex(
            name="idx_source_attempts_run_id",
            table="source_attempts",
            columns=["run_id"],
            purpose="List all provider attempts for a run.",
        ),
        HoldStorageIndex(
            name="idx_source_attempts_strategy",
            table="source_attempts",
            columns=["strategy"],
            purpose="Inspect fallback behavior by strategy.",
        ),
        HoldStorageIndex(
            name="idx_jobs_status",
            table="jobs",
            columns=["status"],
            purpose="List jobs by lifecycle state.",
        ),
        HoldStorageIndex(
            name="idx_jobs_created_at",
            table="jobs",
            columns=["created_at"],
            purpose="Support recent job listing.",
        ),
        HoldStorageIndex(
            name="idx_stream_events_job_id",
            table="stream_events",
            columns=["job_id"],
            purpose="Fetch ordered job event streams.",
        ),
        HoldStorageIndex(
            name="idx_plugin_reports_run_id",
            table="plugin_reports",
            columns=["run_id"],
            purpose="List plugin outcomes per run.",
        ),
        HoldStorageIndex(
            name="idx_plugin_reports_plugin",
            table="plugin_reports",
            columns=["plugin"],
            purpose="Compare plugin performance across runs.",
        ),
        HoldStorageIndex(
            name="idx_evidence_records_run_id",
            table="evidence_records",
            columns=["run_id"],
            purpose="Read evidence chains for a run.",
        ),
        HoldStorageIndex(
            name="idx_evidence_records_entity_id",
            table="evidence_records",
            columns=["entity_id"],
            purpose="Read evidence by entity.",
        ),
        HoldStorageIndex(
            name="idx_evidence_chain_records_run_id",
            table="evidence_chain_records",
            columns=["run_id"],
            purpose="Read evidence chains by run.",
        ),
        HoldStorageIndex(
            name="idx_evidence_chain_records_entity_id",
            table="evidence_chain_records",
            columns=["entity_id"],
            purpose="Read evidence chains by entity.",
        ),
        HoldStorageIndex(
            name="idx_relation_records_run_id",
            table="relation_records",
            columns=["run_id"],
            purpose="Read relations by run.",
        ),
        HoldStorageIndex(
            name="idx_relation_records_schema_name",
            table="relation_records",
            columns=["schema_name"],
            purpose="Filter relations by schema family.",
        ),
        HoldStorageIndex(
            name="idx_relation_records_schema_version",
            table="relation_records",
            columns=["schema_version"],
            purpose="Compare relations across contract versions.",
        ),
        HoldStorageIndex(
            name="idx_relation_records_type",
            table="relation_records",
            columns=["relation_type"],
            purpose="Inspect relation classes.",
        ),
        HoldStorageIndex(
            name="idx_relation_records_from_id",
            table="relation_records",
            columns=["from_entity_id"],
            purpose="Traverse outgoing relations from an entity.",
        ),
        HoldStorageIndex(
            name="idx_relation_records_to_id",
            table="relation_records",
            columns=["to_entity_id"],
            purpose="Traverse incoming relations to an entity.",
        ),
        HoldStorageIndex(
            name="idx_hyperedges_run_id",
            table="hyperedges",
            columns=["run_id"],
            purpose="Read hyperedges by run.",
        ),
        HoldStorageIndex(
            name="idx_hyperedges_type",
            table="hyperedges",
            columns=["hyperedge_type"],
            purpose="Inspect hyperedge classes.",
        ),
        HoldStorageIndex(
            name="idx_hold_schema_registry_name",
            table="hold_schema_registry",
            columns=["schema_name"],
            purpose="Locate the active Hold schema registry entries.",
        ),
        HoldStorageIndex(
            name="idx_hold_schema_registry_versions",
            table="hold_schema_registry",
            columns=["hold_version", "storage_version", "migration_version"],
            purpose="Compare contract versions across migrations.",
        ),
        HoldStorageIndex(
            name="idx_query_family_memory_run_id",
            table="query_family_memory",
            columns=["run_id"],
            purpose="Inspect query-family memory by run.",
        ),
        HoldStorageIndex(
            name="idx_query_family_memory_objective",
            table="query_family_memory",
            columns=["objective"],
            purpose="Group query-family memory by objective.",
        ),
        HoldStorageIndex(
            name="idx_query_family_memory_strategy",
            table="query_family_memory",
            columns=["strategy"],
            purpose="Compare strategy performance.",
        ),
        HoldStorageIndex(
            name="idx_query_family_memory_signature",
            table="query_family_memory",
            columns=["query_signature"],
            purpose="Find repeated successful query shapes.",
        ),
        HoldStorageIndex(
            name="idx_semantic_vectors_kind",
            table="semantic_vectors",
            columns=["vector_kind"],
            purpose="Group vector rows by semantic materialization kind.",
        ),
        HoldStorageIndex(
            name="idx_semantic_vectors_run_id",
            table="semantic_vectors",
            columns=["run_id"],
            purpose="Inspect semantic vectors for a run.",
        ),
        HoldStorageIndex(
            name="idx_semantic_vectors_objective",
            table="semantic_vectors",
            columns=["objective"],
            purpose="Inspect semantic vectors by objective.",
        ),
        HoldStorageIndex(
            name="idx_semantic_vectors_strategy",
            table="semantic_vectors",
            columns=["strategy"],
            purpose="Inspect semantic vectors by retrieval strategy.",
        ),
        HoldStorageIndex(
            name="idx_semantic_vectors_source_id",
            table="semantic_vectors",
            columns=["source_id"],
            purpose="Traverse from vector rows back to query-family memory.",
        ),
    ]

    return HoldStorageCatalog(
        planes=planes,
        tables=tables,
        indexes=indexes,
        notes=[
            "The current backend is SQLite, but the catalog is backend-agnostic.",
            "Logical planes are stable even if physical storage changes later.",
            "Vector-backed and graph-backed projections can be added without breaking the catalog.",
        ],
    )
