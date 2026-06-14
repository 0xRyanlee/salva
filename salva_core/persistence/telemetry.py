"""Telemetry, source attempts, and plugin report reads."""
from __future__ import annotations

import json

from salva_core.schemas import PluginReportRecord, SourceAttemptRecord, TelemetryRecord

from .db import DEFAULT_DB_PATH, get_conn


def list_telemetry(
    run_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
    path: str = DEFAULT_DB_PATH,
) -> tuple[list[TelemetryRecord], int]:
    where = ""
    params: list[object] = []
    if run_id:
        where = "WHERE run_id = ?"
        params.append(run_id)

    with get_conn(path) as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM telemetry_records {where}",
            params,
        ).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT query, round_num, strategy, results_total, results_qualified, avg_score,
                   reject_reasons_json, noise_domains_json, metadata_json
            FROM telemetry_records
            {where}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        ).fetchall()

    items = [
        TelemetryRecord(
            query=row[0],
            round_num=row[1],
            strategy=row[2],
            results_total=row[3],
            results_qualified=row[4],
            avg_score=row[5],
            reject_reasons=json.loads(row[6]),
            noise_domains=json.loads(row[7]),
            metadata=json.loads(row[8]),
        )
        for row in rows
    ]
    return items, int(total)


def list_source_attempts(
    run_id: str | None = None,
    strategy: str | None = None,
    limit: int = 200,
    offset: int = 0,
    path: str = DEFAULT_DB_PATH,
) -> tuple[list[SourceAttemptRecord], int]:
    clauses: list[str] = []
    params: list[object] = []
    if run_id:
        clauses.append("run_id = ?")
        params.append(run_id)
    if strategy:
        clauses.append("strategy = ?")
        params.append(strategy)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    with get_conn(path) as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM source_attempts {where}",
            params,
        ).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT run_id, strategy, base_url, mode, source_class, trust_level,
                   risk_level, recommended_crawl_mode, result_count, succeeded, error, format_used
            FROM source_attempts
            {where}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        ).fetchall()

    items = [
        SourceAttemptRecord(
            run_id=row[0],
            strategy=row[1],
            base_url=row[2],
            mode=row[3],
            source_class=row[4],
            trust_level=row[5],
            risk_level=row[6],
            recommended_crawl_mode=row[7],
            result_count=row[8],
            succeeded=bool(row[9]),
            error=row[10],
            format_used=row[11],
        )
        for row in rows
    ]
    return items, int(total)


def list_plugin_reports(
    run_id: str | None = None,
    plugin: str | None = None,
    limit: int = 200,
    offset: int = 0,
    path: str = DEFAULT_DB_PATH,
) -> tuple[list[PluginReportRecord], int]:
    clauses: list[str] = []
    params: list[object] = []
    if run_id:
        clauses.append("run_id = ?")
        params.append(run_id)
    if plugin:
        clauses.append("plugin = ?")
        params.append(plugin)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    with get_conn(path) as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM plugin_reports {where}",
            params,
        ).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT plugin, target_entity_id, status, applied, message, data_json
            FROM plugin_reports
            {where}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        ).fetchall()

    items = [
        PluginReportRecord(
            plugin=row[0],
            target_entity_id=row[1],
            status=row[2],
            applied=bool(row[3]),
            message=row[4],
            data=json.loads(row[5]),
        )
        for row in rows
    ]
    return items, int(total)
