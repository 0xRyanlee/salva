"""Tenant quota and rate-limit evaluation helpers."""
from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from salva_core.schemas import (
    QuotaPolicy,
    QuotaWindowUsage,
    TenantQuotaResponse,
)

from .persistence import DEFAULT_DB_PATH, list_jobs, list_runs


def load_quota_policy() -> QuotaPolicy:
    policy = QuotaPolicy(
        enabled=False,
        hourly_run_limit=_read_limit("SALVA_TENANT_HOURLY_RUN_LIMIT"),
        daily_run_limit=_read_limit("SALVA_TENANT_DAILY_RUN_LIMIT"),
        hourly_job_limit=_read_limit("SALVA_TENANT_HOURLY_JOB_LIMIT"),
        daily_job_limit=_read_limit("SALVA_TENANT_DAILY_JOB_LIMIT"),
    )
    policy.enabled = any(
        limit is not None and limit > 0
        for limit in (
            policy.hourly_run_limit,
            policy.daily_run_limit,
            policy.hourly_job_limit,
            policy.daily_job_limit,
        )
    )
    return policy


def evaluate_tenant_quota(
    tenant_id: str | None,
    path: str = DEFAULT_DB_PATH,
    policy: QuotaPolicy | None = None,
) -> TenantQuotaResponse:
    resolved_policy = policy or load_quota_policy()
    if not tenant_id:
        return TenantQuotaResponse(
            tenant_id=None,
            generated_at=datetime.now(UTC),
            allowed=not resolved_policy.enabled,
            policy=resolved_policy,
            windows=[],
            violated=["tenant_id_required"] if resolved_policy.enabled else [],
        )

    runs, _ = list_runs(path=path)
    jobs, _ = list_jobs(path=path)
    now = datetime.now(UTC)

    windows = [
        _build_window("hourly", now - timedelta(hours=1), tenant_id, runs, jobs, resolved_policy),
        _build_window("daily", now - timedelta(days=1), tenant_id, runs, jobs, resolved_policy),
    ]

    violated = _collect_violations(windows, resolved_policy)
    return TenantQuotaResponse(
        tenant_id=tenant_id,
        generated_at=now,
        allowed=not violated,
        policy=resolved_policy,
        windows=windows,
        violated=violated,
    )


def _read_limit(name: str) -> int | None:
    raw = os.getenv(name, "").strip()
    if not raw:
        return None
    try:
        limit = int(raw)
    except ValueError:
        return None
    return limit if limit > 0 else None


def _build_window(
    window: Literal["hourly", "daily"],
    since: datetime,
    tenant_id: str,
    runs: list[Any],
    jobs: list[Any],
    policy: QuotaPolicy,
) -> QuotaWindowUsage:
    run_count = sum(
        1
        for run in runs
        if run.created_at >= since and _record_tenant(run.request, run.meta) == tenant_id
    )
    job_count = sum(
        1
        for job in jobs
        if job.created_at >= since and _record_tenant(job.request, job.meta, job.tenant_id) == tenant_id
    )

    if window == "hourly":
        run_limit = policy.hourly_run_limit
        job_limit = policy.hourly_job_limit
    else:
        run_limit = policy.daily_run_limit
        job_limit = policy.daily_job_limit

    return QuotaWindowUsage(
        window=window,
        run_count=run_count,
        job_count=job_count,
        run_limit=run_limit,
        job_limit=job_limit,
        run_remaining=_remaining(run_limit, run_count),
        job_remaining=_remaining(job_limit, job_count),
    )


def _collect_violations(windows: list[QuotaWindowUsage], policy: QuotaPolicy) -> list[str]:
    violations: list[str] = []
    for window in windows:
        if window.window == "hourly":
            if policy.hourly_run_limit is not None and window.run_count >= policy.hourly_run_limit:
                violations.append("hourly_run_limit")
            if policy.hourly_job_limit is not None and window.job_count >= policy.hourly_job_limit:
                violations.append("hourly_job_limit")
        else:
            if policy.daily_run_limit is not None and window.run_count >= policy.daily_run_limit:
                violations.append("daily_run_limit")
            if policy.daily_job_limit is not None and window.job_count >= policy.daily_job_limit:
                violations.append("daily_job_limit")
    return violations


def _remaining(limit: int | None, count: int) -> int | None:
    if limit is None:
        return None
    return max(limit - count, 0)


def _record_tenant(request: dict[str, Any], meta: dict[str, Any], explicit_tenant: str | None = None) -> str | None:
    if explicit_tenant and explicit_tenant.strip():
        return explicit_tenant.strip()
    for payload in (request, meta):
        tenant = payload.get("tenant_id")
        if isinstance(tenant, str) and tenant.strip():
            return tenant.strip()
    return None
