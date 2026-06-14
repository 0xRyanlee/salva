"""
salva_core.persistence — public API re-export shim.

All callers import from salva_core.persistence directly; submodule structure
is an internal detail. External API is unchanged from the monolithic module.
"""
from .db import (
    DEFAULT_DB_PATH,
    FALLBACK_DB_PATH,
    ensure_db,
    get_conn,
    get_db_path_for_project,
)
from .evidence import (
    list_evidence_chains,
    list_evidence_records,
    list_hold_schema_migrations,
    list_hyperedges,
    list_relations,
)
from .hold import (
    add_entity_alias,
    backfill_normalized_aliases,
    get_aliases_for_canonical,
    get_routing_boost,
    list_edges_for_node,
    list_incidences_for_edge,
    list_routing_memory,
    normalize_alias,
    record_probe_result,
    record_source_attempt,
    resolve_canonical_id,
    resolve_entity_normalized,
    upsert_canonical_entity,
    upsert_hyperedge_incidence,
)
from .jobs import (
    append_stream_event,
    claim_next_job,
    create_job,
    get_job,
    get_job_request,
    list_jobs,
    list_stream_events,
    update_job_status,
)
from .memory import (
    list_query_family_memory,
    promote_query_family_memory,
    read_top_query_families_for_seeding,
    search_query_family_memory,
)
from .runs import (
    get_run,
    list_runs,
    persist_discovery_run,
    update_run_meta,
)
from .telemetry import (
    list_plugin_reports,
    list_source_attempts,
    list_telemetry,
)
from .usage import list_usage_telemetry

__all__ = [
    # db
    "DEFAULT_DB_PATH",
    "FALLBACK_DB_PATH",
    "ensure_db",
    "get_conn",
    "get_db_path_for_project",
    # runs
    "get_run",
    "list_runs",
    "persist_discovery_run",
    "update_run_meta",
    # jobs
    "append_stream_event",
    "claim_next_job",
    "create_job",
    "get_job",
    "get_job_request",
    "list_jobs",
    "list_stream_events",
    "update_job_status",
    # telemetry
    "list_plugin_reports",
    "list_source_attempts",
    "list_telemetry",
    "list_usage_telemetry",
    # evidence
    "list_evidence_chains",
    "list_evidence_records",
    "list_hold_schema_migrations",
    "list_hyperedges",
    "list_relations",
    # memory
    "list_query_family_memory",
    "promote_query_family_memory",
    "read_top_query_families_for_seeding",
    "search_query_family_memory",
    # hold — typed n-ary incidence, canonical entity registry, routing memory
    "add_entity_alias",
    "backfill_normalized_aliases",
    "get_aliases_for_canonical",
    "get_routing_boost",
    "list_edges_for_node",
    "list_incidences_for_edge",
    "list_routing_memory",
    "normalize_alias",
    "record_probe_result",
    "record_source_attempt",
    "resolve_canonical_id",
    "resolve_entity_normalized",
    "upsert_canonical_entity",
    "upsert_hyperedge_incidence",
]
