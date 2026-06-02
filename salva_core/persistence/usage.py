"""Usage telemetry aggregation helpers."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from salva_core.schemas import TenantUsageRecord, UsageTelemetryResponse

from .db import DEFAULT_DB_PATH, get_conn


def list_usage_telemetry(
    tenant_id: str | None = None,
    path: str = DEFAULT_DB_PATH,
) -> UsageTelemetryResponse:
    records: dict[str, TenantUsageRecord] = {}

    with get_conn(path) as conn:
        run_rows = conn.execute(
            """
            SELECT run_id, request_json, meta_json, created_at
            FROM discovery_runs
            ORDER BY created_at DESC
            """
        ).fetchall()
        job_rows = conn.execute(
            """
            SELECT request_json, meta_json, status, created_at
            FROM jobs
            ORDER BY created_at DESC
            """
        ).fetchall()
        telemetry_rows = conn.execute(
            """
            SELECT run_id, COUNT(*) AS item_count
            FROM telemetry_records
            GROUP BY run_id
            """
        ).fetchall()
        source_attempt_rows = conn.execute(
            """
            SELECT run_id, COUNT(*) AS item_count
            FROM source_attempts
            GROUP BY run_id
            """
        ).fetchall()

    total_runs = 0
    total_jobs = 0
    run_tenants: dict[str, str] = {}

    for run_id, request_json, meta_json, created_at in run_rows:
        request = _safe_json_loads(request_json)
        meta = _safe_json_loads(meta_json)
        resolved_tenant = _resolve_tenant_id(request, meta)
        if not _matches_tenant(resolved_tenant, tenant_id):
            continue
        if resolved_tenant is None:
            resolved_tenant = "unassigned"
        run_tenants[run_id] = resolved_tenant
        total_runs += 1
        record = records.setdefault(resolved_tenant, TenantUsageRecord(tenant_id=resolved_tenant))
        record.run_count += 1
        record.raw_count += int(meta.get("raw_count", 0) or 0)
        record.qualified_count += int(meta.get("qualified_count", 0) or 0)
        _update_latest(record, created_at, is_run=True)
        _merge_provider_kinds(record.provider_kinds, meta.get("provider_kinds"))

    for request_json, meta_json, status, created_at in job_rows:
        request = _safe_json_loads(request_json)
        meta = _safe_json_loads(meta_json)
        resolved_tenant = _resolve_tenant_id(request, meta)
        if not _matches_tenant(resolved_tenant, tenant_id):
            continue
        if resolved_tenant is None:
            resolved_tenant = "unassigned"
        total_jobs += 1
        record = records.setdefault(resolved_tenant, TenantUsageRecord(tenant_id=resolved_tenant))
        record.job_count += 1
        if status == "completed":
            record.completed_job_count += 1
        elif status == "failed":
            record.failed_job_count += 1
        elif status == "queued":
            record.queued_job_count += 1
        elif status == "running":
            record.running_job_count += 1
        _update_latest(record, created_at, is_run=False)
        _merge_provider_kinds(record.provider_kinds, meta.get("provider_kinds"))

    for run_id, item_count in telemetry_rows:
        resolved_tenant = run_tenants.get(run_id)
        if resolved_tenant is None:
            continue
        record = records.setdefault(resolved_tenant, TenantUsageRecord(tenant_id=resolved_tenant))
        record.telemetry_count += int(item_count or 0)

    for run_id, item_count in source_attempt_rows:
        resolved_tenant = run_tenants.get(run_id)
        if resolved_tenant is None:
            continue
        record = records.setdefault(resolved_tenant, TenantUsageRecord(tenant_id=resolved_tenant))
        record.source_attempt_count += int(item_count or 0)

    items = sorted(records.values(), key=lambda item: (item.run_count + item.job_count, item.tenant_id), reverse=True)
    return UsageTelemetryResponse(
        generated_at=datetime.now(UTC),
        tenant_id=tenant_id,
        total_runs=total_runs,
        total_jobs=total_jobs,
        total_tenants=len(items),
        items=items,
    )


def _safe_json_loads(value: str | None) -> dict[str, Any]:
    import json

    if not value:
        return {}
    try:
        data = json.loads(value)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _resolve_tenant_id(request: dict[str, Any], meta: dict[str, Any]) -> str | None:
    for payload in (request, meta):
        tenant = payload.get("tenant_id")
        if isinstance(tenant, str) and tenant.strip():
            return tenant.strip()
    return None


def _matches_tenant(resolved_tenant: str | None, filter_tenant: str | None) -> bool:
    if filter_tenant is None:
        return True
    if filter_tenant == "unassigned":
        return resolved_tenant is None
    return resolved_tenant == filter_tenant


def _update_latest(record: TenantUsageRecord, created_at: str, *, is_run: bool) -> None:
    try:
        timestamp = datetime.fromisoformat(created_at)
    except Exception:
        return

    if is_run:
        if record.latest_run_at is None or timestamp > record.latest_run_at:
            record.latest_run_at = timestamp
    else:
        if record.latest_job_at is None or timestamp > record.latest_job_at:
            record.latest_job_at = timestamp


def _merge_provider_kinds(dest: list[str], source: Any) -> None:
    if not isinstance(source, list):
        return
    seen = set(dest)
    for item in source:
        if isinstance(item, str) and item not in seen:
            dest.append(item)
            seen.add(item)
