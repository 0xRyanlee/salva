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
)
from .runs import (
    get_run,
    list_runs,
    persist_discovery_run,
    update_run_meta,
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
from .telemetry import (
    list_plugin_reports,
    list_source_attempts,
    list_telemetry,
)
from .usage import list_usage_telemetry
from .evidence import (
    list_evidence_chains,
    list_evidence_records,
    list_hold_schema_migrations,
    list_hyperedges,
    list_relations,
)
from .memory import (
    list_query_family_memory,
    read_top_query_families_for_seeding,
    search_query_family_memory,
)

__all__ = [
    # db
    "DEFAULT_DB_PATH",
    "FALLBACK_DB_PATH",
    "ensure_db",
    "get_conn",
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
    "read_top_query_families_for_seeding",
    "search_query_family_memory",
]
