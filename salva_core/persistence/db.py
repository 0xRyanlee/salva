"""
Database setup, connection management, schema migration, and utility helpers.

All other persistence submodules import get_conn and DEFAULT_DB_PATH from here.
"""
from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from hold.schema import build_hold_schema

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = os.getenv(
    "SALVA_SQLITE_PATH",
    str(PROJECT_ROOT / "data" / "salva_runtime.db"),
)
FALLBACK_DB_PATH = os.getenv(
    "SALVA_SQLITE_FALLBACK_PATH",
    str(Path(tempfile.gettempdir()) / "salva_runtime.db"),
)

_SAFE_PROJECT_ID_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
)


def get_db_path_for_project(project_id: str | None) -> str:
    """Return the SQLite path for a project, or DEFAULT_DB_PATH if project_id is None."""
    if not project_id:
        return DEFAULT_DB_PATH
    safe = "".join(c for c in project_id if c in _SAFE_PROJECT_ID_CHARS)
    if not safe:
        return DEFAULT_DB_PATH
    data_dir = Path(DEFAULT_DB_PATH).parent
    return str(data_dir / "projects" / safe / "salva.db")


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS discovery_runs (
    run_id TEXT PRIMARY KEY,
    objective TEXT NOT NULL,
    output_profile TEXT NOT NULL,
    campaign_id TEXT,
    continuation_id TEXT,
    persistence_mode TEXT NOT NULL DEFAULT 'audit',
    request_json TEXT NOT NULL,
    entities_json TEXT NOT NULL,
    relations_json TEXT NOT NULL,
    meta_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS telemetry_records (
    telemetry_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    query TEXT NOT NULL,
    round_num INTEGER NOT NULL,
    strategy TEXT NOT NULL,
    results_total INTEGER NOT NULL,
    results_qualified INTEGER NOT NULL,
    avg_score REAL NOT NULL,
    reject_reasons_json TEXT NOT NULL,
    noise_domains_json TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES discovery_runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_telemetry_run_id ON telemetry_records(run_id);
CREATE INDEX IF NOT EXISTS idx_telemetry_query ON telemetry_records(query);

CREATE TABLE IF NOT EXISTS source_attempts (
    attempt_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    strategy TEXT NOT NULL,
    base_url TEXT NOT NULL,
    mode TEXT NOT NULL,
    source_class TEXT,
    trust_level TEXT,
    risk_level TEXT,
    recommended_crawl_mode TEXT,
    result_count INTEGER NOT NULL,
    succeeded INTEGER NOT NULL,
    error TEXT,
    format_used TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES discovery_runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_source_attempts_run_id ON source_attempts(run_id);
CREATE INDEX IF NOT EXISTS idx_source_attempts_strategy ON source_attempts(strategy);

CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    objective TEXT NOT NULL,
    output_profile TEXT NOT NULL,
    tenant_id TEXT,
    request_json TEXT NOT NULL,
    run_id TEXT,
    error TEXT,
    worker_id TEXT,
    meta_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at);

CREATE TABLE IF NOT EXISTS stream_events (
    event_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    message TEXT NOT NULL,
    data_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
);

CREATE INDEX IF NOT EXISTS idx_stream_events_job_id ON stream_events(job_id);

CREATE TABLE IF NOT EXISTS plugin_reports (
    report_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    plugin TEXT NOT NULL,
    target_entity_id TEXT NOT NULL,
    status TEXT NOT NULL,
    applied INTEGER NOT NULL,
    message TEXT,
    data_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES discovery_runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_plugin_reports_run_id ON plugin_reports(run_id);
CREATE INDEX IF NOT EXISTS idx_plugin_reports_plugin ON plugin_reports(plugin);

CREATE TABLE IF NOT EXISTS evidence_records (
    evidence_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    source_url TEXT NOT NULL,
    source_name TEXT,
    title TEXT,
    snippet TEXT,
    captured_at TEXT,
    metadata_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES discovery_runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_evidence_records_run_id ON evidence_records(run_id);
CREATE INDEX IF NOT EXISTS idx_evidence_records_entity_id ON evidence_records(entity_id);

CREATE TABLE IF NOT EXISTS evidence_chain_records (
    chain_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    entity_title TEXT,
    evidence_ids_json TEXT NOT NULL,
    relation_ids_json TEXT NOT NULL,
    hyperedge_ids_json TEXT NOT NULL,
    links_json TEXT NOT NULL,
    first_captured_at TEXT,
    last_captured_at TEXT,
    evidence_count INTEGER NOT NULL,
    relation_count INTEGER NOT NULL,
    hyperedge_count INTEGER NOT NULL,
    notes_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES discovery_runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_evidence_chain_records_run_id ON evidence_chain_records(run_id);
CREATE INDEX IF NOT EXISTS idx_evidence_chain_records_entity_id ON evidence_chain_records(entity_id);

CREATE TABLE IF NOT EXISTS relation_records (
    record_id TEXT PRIMARY KEY,
    relation_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    schema_name TEXT NOT NULL DEFAULT 'canonical_relation',
    schema_version TEXT NOT NULL DEFAULT '0.1.0',
    storage_version TEXT NOT NULL DEFAULT '0.1.0',
    migration_version TEXT NOT NULL DEFAULT '0.1.0',
    relation_type TEXT NOT NULL,
    from_entity_id TEXT NOT NULL,
    to_entity_id TEXT NOT NULL,
    confidence REAL NOT NULL,
    evidence_ids_json TEXT NOT NULL,
    attributes_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES discovery_runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_relation_records_run_id ON relation_records(run_id);
CREATE INDEX IF NOT EXISTS idx_relation_records_relation_id ON relation_records(relation_id);
CREATE INDEX IF NOT EXISTS idx_relation_records_type ON relation_records(relation_type);
CREATE INDEX IF NOT EXISTS idx_relation_records_from_id ON relation_records(from_entity_id);
CREATE INDEX IF NOT EXISTS idx_relation_records_to_id ON relation_records(to_entity_id);

CREATE TABLE IF NOT EXISTS hyperedges (
    hyperedge_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    hyperedge_type TEXT NOT NULL,
    summary TEXT,
    confidence REAL NOT NULL,
    evidence_ids_json TEXT NOT NULL,
    source_ids_json TEXT NOT NULL,
    members_json TEXT NOT NULL,
    properties_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES discovery_runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_hyperedges_run_id ON hyperedges(run_id);
CREATE INDEX IF NOT EXISTS idx_hyperedges_type ON hyperedges(hyperedge_type);

-- Typed n-ary incidence table: each row = one node's participation in a hyperedge with a role.
-- This is the canonical n-ary representation; members_json in hyperedges is a legacy summary.
CREATE TABLE IF NOT EXISTS hyperedge_incidences (
    hyperedge_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    role TEXT NOT NULL,
    percentage REAL,
    order_index INTEGER NOT NULL DEFAULT 0,
    props_json TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY (hyperedge_id, node_id, role),
    FOREIGN KEY (hyperedge_id) REFERENCES hyperedges(hyperedge_id)
);

CREATE INDEX IF NOT EXISTS idx_hei_hyperedge ON hyperedge_incidences(hyperedge_id);
CREATE INDEX IF NOT EXISTS idx_hei_node ON hyperedge_incidences(node_id);
CREATE INDEX IF NOT EXISTS idx_hei_role ON hyperedge_incidences(role);

-- Canonical entity registry: one row per resolved real-world entity.
-- entity_id in discovery results maps to canonical_id via entity_aliases.
CREATE TABLE IF NOT EXISTS canonical_entities (
    canonical_id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    primary_label TEXT NOT NULL,
    jurisdiction TEXT,
    props_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

-- Cross-lingual and cross-source aliases for canonical entities.
-- Used for gazetteer-based entity resolution (Jina embedding bridge deferred).
CREATE TABLE IF NOT EXISTS entity_aliases (
    alias_id TEXT PRIMARY KEY,
    canonical_id TEXT NOT NULL,
    alias TEXT NOT NULL,
    script TEXT,
    source TEXT,
    FOREIGN KEY (canonical_id) REFERENCES canonical_entities(canonical_id)
);

CREATE INDEX IF NOT EXISTS idx_entity_aliases_canonical ON entity_aliases(canonical_id);
CREATE INDEX IF NOT EXISTS idx_entity_aliases_alias ON entity_aliases(alias);

-- Cross-run routing memory: aggregates source_attempts for persistent routing optimisation.
-- authority_boost increases on success; is decremented on failure.
CREATE TABLE IF NOT EXISTS routing_memory (
    source_url TEXT PRIMARY KEY,
    success_count INTEGER NOT NULL DEFAULT 0,
    failure_count INTEGER NOT NULL DEFAULT 0,
    last_success_at TEXT,
    last_failure_at TEXT,
    authority_boost REAL NOT NULL DEFAULT 0.0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS hold_schema_registry (
    registry_id TEXT PRIMARY KEY,
    schema_name TEXT NOT NULL,
    hold_version TEXT NOT NULL,
    storage_version TEXT NOT NULL,
    migration_version TEXT NOT NULL,
    migration_strategy TEXT NOT NULL,
    status TEXT NOT NULL,
    details_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_hold_schema_registry_name ON hold_schema_registry(schema_name);
CREATE INDEX IF NOT EXISTS idx_hold_schema_registry_versions ON hold_schema_registry(hold_version, storage_version, migration_version);

CREATE TABLE IF NOT EXISTS query_family_memory (
    memory_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    campaign_id TEXT,
    continuation_id TEXT,
    memory_status TEXT NOT NULL DEFAULT 'legacy',
    promoted_at TEXT,
    domain TEXT NOT NULL,
    objective TEXT NOT NULL,
    output_profile TEXT NOT NULL,
    round_num INTEGER NOT NULL,
    strategy TEXT NOT NULL,
    query TEXT NOT NULL,
    query_signature TEXT NOT NULL,
    source_nodes_json TEXT NOT NULL,
    content_weights_json TEXT NOT NULL,
    source_hints_json TEXT NOT NULL,
    notes_json TEXT NOT NULL,
    raw_total INTEGER NOT NULL,
    qualified_total INTEGER NOT NULL,
    avg_score REAL NOT NULL,
    success_score REAL NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES discovery_runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_query_family_memory_run_id ON query_family_memory(run_id);
CREATE INDEX IF NOT EXISTS idx_query_family_memory_objective ON query_family_memory(objective);
CREATE INDEX IF NOT EXISTS idx_query_family_memory_strategy ON query_family_memory(strategy);
CREATE INDEX IF NOT EXISTS idx_query_family_memory_signature ON query_family_memory(query_signature);

CREATE TABLE IF NOT EXISTS semantic_vectors (
    vector_id TEXT PRIMARY KEY,
    vector_kind TEXT NOT NULL,
    source_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    objective TEXT NOT NULL,
    output_profile TEXT NOT NULL,
    strategy TEXT NOT NULL,
    text TEXT NOT NULL,
    embedding_json TEXT NOT NULL,
    dimensions INTEGER NOT NULL,
    norm REAL NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (source_id) REFERENCES query_family_memory(memory_id),
    FOREIGN KEY (run_id) REFERENCES discovery_runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_semantic_vectors_kind ON semantic_vectors(vector_kind);
CREATE INDEX IF NOT EXISTS idx_semantic_vectors_run_id ON semantic_vectors(run_id);
CREATE INDEX IF NOT EXISTS idx_semantic_vectors_objective ON semantic_vectors(objective);
CREATE INDEX IF NOT EXISTS idx_semantic_vectors_strategy ON semantic_vectors(strategy);
CREATE INDEX IF NOT EXISTS idx_semantic_vectors_source_id ON semantic_vectors(source_id);
"""


def ensure_db(path: str = DEFAULT_DB_PATH) -> str:
    last_error: sqlite3.OperationalError | None = None
    for db_path in _resolve_db_paths(path):
        try:
            db_path.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(db_path) as conn:
                conn.executescript(SCHEMA_SQL)
                _migrate_schema(conn)
                _ensure_hold_schema_registry(conn)
                _probe_writable(conn)
                conn.commit()
            return str(db_path)
        except sqlite3.OperationalError as exc:
            last_error = exc
            continue

    raise last_error or sqlite3.OperationalError("unable to initialize sqlite database")


@contextmanager
def get_conn(path: str = DEFAULT_DB_PATH) -> Iterator[sqlite3.Connection]:
    resolved_path = ensure_db(path)
    conn = sqlite3.connect(resolved_path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _resolve_db_path(path: str) -> Path:
    return _resolve_db_paths(path)[0]


def _resolve_db_paths(path: str) -> list[Path]:
    candidates = [Path(path), Path(FALLBACK_DB_PATH)]
    resolved: list[Path] = []
    for candidate in candidates:
        if candidate.exists() and not os.access(candidate, os.W_OK):
            continue
        parent = candidate.parent
        if parent.exists() and not os.access(parent, os.W_OK):
            continue
        resolved.append(candidate)

    return resolved or candidates


def _probe_writable(conn: sqlite3.Connection) -> None:
    probe_name = f"__salva_write_probe_{uuid.uuid4().hex}"
    conn.execute("SAVEPOINT salva_write_probe")
    try:
        conn.execute(f'CREATE TABLE "{probe_name}" (id INTEGER)')
        conn.execute("ROLLBACK TO salva_write_probe")
        conn.execute("RELEASE salva_write_probe")
    except sqlite3.OperationalError:
        try:
            conn.execute("ROLLBACK TO salva_write_probe")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("RELEASE salva_write_probe")
        except sqlite3.OperationalError:
            pass
        raise


def _migrate_schema(conn: sqlite3.Connection) -> None:
    discovery_run_columns = {
        row[1] for row in conn.execute("PRAGMA table_info(discovery_runs)").fetchall()
    }
    discovery_run_required_columns = {
        "campaign_id": "TEXT",
        "continuation_id": "TEXT",
        "persistence_mode": "TEXT NOT NULL DEFAULT 'audit'",
        "project_id": "TEXT",
    }
    for column, sql_type in discovery_run_required_columns.items():
        if column not in discovery_run_columns:
            conn.execute(f"ALTER TABLE discovery_runs ADD COLUMN {column} {sql_type}")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_discovery_runs_campaign "
        "ON discovery_runs(campaign_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_discovery_runs_continuation "
        "ON discovery_runs(continuation_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_discovery_runs_project "
        "ON discovery_runs(project_id)"
    )

    job_columns = {
        row[1] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()
    }
    if "project_id" not in job_columns:
        conn.execute("ALTER TABLE jobs ADD COLUMN project_id TEXT")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_project ON jobs(project_id)")

    source_attempt_columns = {
        row[1] for row in conn.execute("PRAGMA table_info(source_attempts)").fetchall()
    }
    required_columns = {
        "source_class": "TEXT",
        "trust_level": "TEXT",
        "risk_level": "TEXT",
        "recommended_crawl_mode": "TEXT",
    }
    for column, sql_type in required_columns.items():
        if column not in source_attempt_columns:
            conn.execute(f"ALTER TABLE source_attempts ADD COLUMN {column} {sql_type}")

    relation_columns = {
        row[1] for row in conn.execute("PRAGMA table_info(relation_records)").fetchall()
    }
    relation_required_columns = {
        "record_id": "TEXT",
        "schema_name": "TEXT NOT NULL DEFAULT 'canonical_relation'",
        "schema_version": "TEXT NOT NULL DEFAULT '0.1.0'",
        "storage_version": "TEXT NOT NULL DEFAULT '0.1.0'",
        "migration_version": "TEXT NOT NULL DEFAULT '0.1.0'",
    }
    if "record_id" not in relation_columns:
        conn.execute("ALTER TABLE relation_records RENAME TO relation_records_legacy")
        conn.execute(
            """
            CREATE TABLE relation_records (
                record_id TEXT PRIMARY KEY,
                relation_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                schema_name TEXT NOT NULL DEFAULT 'canonical_relation',
                schema_version TEXT NOT NULL DEFAULT '0.1.0',
                storage_version TEXT NOT NULL DEFAULT '0.1.0',
                migration_version TEXT NOT NULL DEFAULT '0.1.0',
                relation_type TEXT NOT NULL,
                from_entity_id TEXT NOT NULL,
                to_entity_id TEXT NOT NULL,
                confidence REAL NOT NULL,
                evidence_ids_json TEXT NOT NULL,
                attributes_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES discovery_runs(run_id)
            )
            """
        )
        conn.execute(
            """
            INSERT INTO relation_records (
                record_id, relation_id, run_id, schema_name, schema_version,
                storage_version, migration_version, relation_type, from_entity_id,
                to_entity_id, confidence, evidence_ids_json, attributes_json, created_at
            )
            SELECT
                lower(hex(randomblob(16))),
                relation_id, run_id, schema_name, schema_version,
                storage_version, migration_version, relation_type, from_entity_id,
                to_entity_id, confidence, evidence_ids_json, attributes_json, created_at
            FROM relation_records_legacy
            """
        )
        conn.execute("DROP TABLE relation_records_legacy")
        relation_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(relation_records)").fetchall()
        }
    for column, sql_type in relation_required_columns.items():
        if column not in relation_columns:
            conn.execute(f"ALTER TABLE relation_records ADD COLUMN {column} {sql_type}")
    for index_sql in (
        "CREATE INDEX IF NOT EXISTS idx_relation_records_schema_name ON relation_records(schema_name)",
        "CREATE INDEX IF NOT EXISTS idx_relation_records_schema_version ON relation_records(schema_version)",
        "CREATE INDEX IF NOT EXISTS idx_relation_records_relation_id ON relation_records(relation_id)",
    ):
        conn.execute(index_sql)

    job_columns = {
        row[1] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()
    }
    if "worker_id" not in job_columns:
        conn.execute("ALTER TABLE jobs ADD COLUMN worker_id TEXT")
    if "tenant_id" not in job_columns:
        conn.execute("ALTER TABLE jobs ADD COLUMN tenant_id TEXT")

    query_family_columns = {
        row[1] for row in conn.execute("PRAGMA table_info(query_family_memory)").fetchall()
    }
    if "domain" not in query_family_columns:
        conn.execute("ALTER TABLE query_family_memory ADD COLUMN domain TEXT NOT NULL DEFAULT 'general'")
    if "content_nodes_json" not in query_family_columns:
        conn.execute("ALTER TABLE query_family_memory ADD COLUMN content_nodes_json TEXT NOT NULL DEFAULT '[]'")
    query_family_required_columns = {
        "campaign_id": "TEXT",
        "continuation_id": "TEXT",
        "memory_status": "TEXT NOT NULL DEFAULT 'legacy'",
        "promoted_at": "TEXT",
    }
    for column, sql_type in query_family_required_columns.items():
        if column not in query_family_columns:
            conn.execute(f"ALTER TABLE query_family_memory ADD COLUMN {column} {sql_type}")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_query_family_memory_domain ON query_family_memory(domain)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_query_family_memory_campaign "
        "ON query_family_memory(campaign_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_query_family_memory_status "
        "ON query_family_memory(memory_status)"
    )

    # Ensure new Hold upgrade tables exist (idempotent — CREATE IF NOT EXISTS handles re-runs)
    for create_sql in (
        """CREATE TABLE IF NOT EXISTS hyperedge_incidences (
            hyperedge_id TEXT NOT NULL, node_id TEXT NOT NULL, role TEXT NOT NULL,
            percentage REAL, order_index INTEGER NOT NULL DEFAULT 0,
            props_json TEXT NOT NULL DEFAULT '{}',
            PRIMARY KEY (hyperedge_id, node_id, role))""",
        "CREATE INDEX IF NOT EXISTS idx_hei_hyperedge ON hyperedge_incidences(hyperedge_id)",
        "CREATE INDEX IF NOT EXISTS idx_hei_node ON hyperedge_incidences(node_id)",
        """CREATE TABLE IF NOT EXISTS canonical_entities (
            canonical_id TEXT PRIMARY KEY, entity_type TEXT NOT NULL,
            primary_label TEXT NOT NULL, jurisdiction TEXT,
            props_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL)""",
        """CREATE TABLE IF NOT EXISTS entity_aliases (
            alias_id TEXT PRIMARY KEY, canonical_id TEXT NOT NULL,
            alias TEXT NOT NULL, script TEXT, source TEXT)""",
        "CREATE INDEX IF NOT EXISTS idx_entity_aliases_canonical ON entity_aliases(canonical_id)",
        "CREATE INDEX IF NOT EXISTS idx_entity_aliases_alias ON entity_aliases(alias)",
        """CREATE TABLE IF NOT EXISTS routing_memory (
            source_url TEXT PRIMARY KEY,
            success_count INTEGER NOT NULL DEFAULT 0,
            failure_count INTEGER NOT NULL DEFAULT 0,
            last_success_at TEXT, last_failure_at TEXT,
            authority_boost REAL NOT NULL DEFAULT 0.0,
            updated_at TEXT NOT NULL)""",
    ):
        conn.execute(create_sql)


def _ensure_hold_schema_registry(conn: sqlite3.Connection) -> None:
    schema = build_hold_schema()
    details = {
        "boundary_rules": [rule.model_dump(mode="json") for rule in schema.boundary_rules],
        "capabilities": [capability.model_dump(mode="json") for capability in schema.capabilities],
        "entity_types": schema.entity_types,
        "relation_types": schema.relation_types,
        "hyperedge_types": schema.hyperedge_types,
        "projection_modes": schema.projection_modes,
        "storage_planes": schema.storage_planes,
        "event_planes": schema.event_planes,
        "migration_notes": schema.migration_notes,
    }
    existing = conn.execute(
        """
        SELECT registry_id
        FROM hold_schema_registry
        WHERE schema_name = ? AND hold_version = ? AND storage_version = ? AND migration_version = ?
        LIMIT 1
        """,
        (
            schema.name,
            schema.version,
            schema.storage_version,
            schema.migration_version,
        ),
    ).fetchone()
    if existing is not None:
        return

    conn.execute(
        """
        INSERT INTO hold_schema_registry (
            registry_id, schema_name, hold_version, storage_version,
            migration_version, migration_strategy, status, details_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            f"hold_schema:{schema.name}:{schema.version}:{schema.storage_version}:{schema.migration_version}",
            schema.name,
            schema.version,
            schema.storage_version,
            schema.migration_version,
            schema.migration_strategy,
            schema.status,
            json.dumps(details, ensure_ascii=False),
            datetime.now(UTC).isoformat(),
        ),
    )
