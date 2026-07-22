import asyncio
import sqlite3
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from apps.api import main
from salva_core.persistence import create_job, persist_discovery_run
from salva_core.quotas import evaluate_tenant_quota
from salva_core.schemas import (
    DiscoveryIntent,
    DiscoveryRequest,
    JobCreateRequest,
    JobRecord,
    QuotaPolicy,
    TenantQuotaResponse,
)


def test_quota_evaluation_aggregates_runs_and_jobs(tmp_path) -> None:
    db_path = str(tmp_path / "salva_quota.db")
    tenant = "tenant-quota"
    request = DiscoveryRequest(
        objective="find_leads",
        tenant_id=tenant,
        intent=DiscoveryIntent(market="Germany", industry="software"),
    )

    run_id = persist_discovery_run(
        request=request,
        entities=[],
        relations=[],
        telemetry=[],
        meta={"qualified_count": 2, "raw_count": 5, "provider_kinds": []},
        source_attempts=[],
        path=db_path,
    )

    from salva_core.persistence import update_job_status

    job_id = create_job(request, path=db_path)
    update_job_status(job_id, "completed", run_id=run_id, path=db_path)

    policy = QuotaPolicy(
        enabled=True,
        hourly_run_limit=10,
        daily_run_limit=10,
        hourly_job_limit=10,
        daily_job_limit=10,
    )
    quota = evaluate_tenant_quota(tenant, path=db_path, policy=policy)

    assert quota.allowed is True
    assert quota.tenant_id == tenant
    assert quota.windows[0].run_count == 1
    assert quota.windows[0].job_count == 1
    assert quota.windows[0].run_remaining == 9
    assert quota.windows[0].job_remaining == 9


def _backdate_run(db_path: str, run_id: str, when: datetime) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE discovery_runs SET created_at = ? WHERE run_id = ?",
            (when.isoformat(), run_id),
        )
        conn.commit()


def _backdate_job(db_path: str, job_id: str, when: datetime) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE jobs SET created_at = ? WHERE job_id = ?",
            (when.isoformat(), job_id),
        )
        conn.commit()


def test_quota_evaluation_not_truncated_by_other_tenant_volume(tmp_path) -> None:
    """Regression test: quota windows must reflect the target tenant's real usage
    even when >20 other-tenant runs/jobs exist and were persisted more recently.
    Before the fix, quotas.py paginated via list_runs()/list_jobs() (default
    limit=20, globally ordered by created_at DESC) and filtered in Python -- so a
    tenant's older-but-still-in-window records could be pushed off the page by
    unrelated tenants' newer records, silently undercounting usage.
    """
    db_path = str(tmp_path / "salva_quota_truncation.db")
    target_tenant = "tenant-target"
    other_tenant = "tenant-other"
    now = datetime.now(UTC)

    def make_request(tenant: str) -> DiscoveryRequest:
        return DiscoveryRequest(
            objective="find_leads",
            tenant_id=tenant,
            intent=DiscoveryIntent(market="Germany", industry="software"),
        )

    def persist_run(tenant: str) -> str:
        return persist_discovery_run(
            request=make_request(tenant),
            entities=[],
            relations=[],
            telemetry=[],
            meta={"qualified_count": 0, "raw_count": 0, "provider_kinds": []},
            source_attempts=[],
            path=db_path,
        )

    # Target tenant: 3 runs inside the hourly window, 2 inside the daily-only
    # window (backdated 2h), 1 outside both windows (backdated 2d).
    for _ in range(3):
        persist_run(target_tenant)
    for _ in range(2):
        _backdate_run(db_path, persist_run(target_tenant), now - timedelta(hours=2))
    _backdate_run(db_path, persist_run(target_tenant), now - timedelta(days=2))

    # Target tenant: 2 jobs inside the hourly window, 1 inside the daily-only window.
    for _ in range(2):
        create_job(make_request(target_tenant), path=db_path)
    _backdate_job(
        db_path,
        create_job(make_request(target_tenant), path=db_path),
        now - timedelta(hours=3),
    )

    # Flood with >20 other-tenant runs/jobs, persisted after the target tenant's
    # records -- under the old top-N pagination bug this pushes every target
    # tenant row off the page (they'd all sort below the newer other-tenant rows).
    for _ in range(25):
        persist_run(other_tenant)
        create_job(make_request(other_tenant), path=db_path)

    policy = QuotaPolicy(
        enabled=True,
        hourly_run_limit=100,
        daily_run_limit=100,
        hourly_job_limit=100,
        daily_job_limit=100,
    )
    quota = evaluate_tenant_quota(target_tenant, path=db_path, policy=policy)

    hourly = next(w for w in quota.windows if w.window == "hourly")
    daily = next(w for w in quota.windows if w.window == "daily")

    assert hourly.run_count == 3
    assert daily.run_count == 5  # 3 recent + 2 backdated-2h; the 2d-old run is excluded
    assert hourly.job_count == 2
    assert daily.job_count == 3  # 2 recent + 1 backdated-3h
    assert quota.allowed is True
    assert quota.violated == []


def test_quota_requires_tenant_when_policy_enabled() -> None:
    policy = QuotaPolicy(
        enabled=True,
        hourly_run_limit=10,
        daily_run_limit=10,
        hourly_job_limit=10,
        daily_job_limit=10,
    )
    quota = evaluate_tenant_quota(None, policy=policy)

    assert quota.allowed is False
    assert quota.violated == ["tenant_id_required"]


def test_quota_endpoint_returns_read_model(monkeypatch) -> None:
    expected = TenantQuotaResponse(
        tenant_id="tenant-x",
        generated_at=datetime.now(UTC),
        allowed=True,
    )
    monkeypatch.setattr(main, "evaluate_tenant_quota", lambda tenant_id=None: expected)

    client = TestClient(main.app)
    response = client.get("/v1/quota", params={"tenant_id": "tenant-x"})

    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == "tenant-x"
    assert body["allowed"] is True


def test_discover_rejects_when_quota_blocked(monkeypatch) -> None:
    blocked = TenantQuotaResponse(
        tenant_id="tenant-blocked",
        generated_at=datetime.now(UTC),
        allowed=False,
        violated=["daily_run_limit"],
    )
    monkeypatch.setattr(main, "evaluate_tenant_quota", lambda tenant_id=None: blocked)
    monkeypatch.setattr(main.service, "run_discovery", lambda discovery: (_ for _ in ()).throw(AssertionError("should not run")))

    payload = DiscoveryRequest(
        objective="find_companies",
        tenant_id="tenant-blocked",
        intent=DiscoveryIntent(market="US", industry="software"),
    )

    with pytest.raises(HTTPException, match="Tenant quota blocked discover"):
        asyncio.run(main.discover(payload))


def test_discover_binds_configured_tenant_when_quota_enabled(monkeypatch) -> None:
    monkeypatch.setattr(main, "load_quota_policy", lambda: QuotaPolicy(
        enabled=True,
        hourly_run_limit=10,
        daily_run_limit=10,
        hourly_job_limit=10,
        daily_job_limit=10,
    ))
    monkeypatch.setenv("SALVA_TENANT_ID", "tenant-bound")

    captured = {}

    def fake_run_discovery(payload):
        captured["tenant_id"] = payload.tenant_id
        return ([], [], [], {"qualified_count": 0, "tenant_id": payload.tenant_id})

    monkeypatch.setattr(main.service, "run_discovery", fake_run_discovery)

    payload = DiscoveryRequest(
        objective="find_companies",
        intent=DiscoveryIntent(market="US", industry="software"),
    )

    response = asyncio.run(main.discover(payload))

    assert response.meta["tenant_id"] == "tenant-bound"
    assert captured["tenant_id"] == "tenant-bound"


def test_job_creation_rejects_when_quota_blocked(monkeypatch) -> None:
    blocked = TenantQuotaResponse(
        tenant_id="tenant-blocked",
        generated_at=datetime.now(UTC),
        allowed=False,
        violated=["daily_job_limit"],
    )
    monkeypatch.setattr(main, "evaluate_tenant_quota", lambda tenant_id=None: blocked)
    monkeypatch.setattr(main, "create_job", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should not create")))

    payload = JobCreateRequest(
        discovery=DiscoveryRequest(
            objective="find_leads",
            tenant_id="tenant-blocked",
            intent=DiscoveryIntent(market="Germany", industry="software"),
        )
    )

    with pytest.raises(HTTPException, match="Tenant quota blocked job"):
        asyncio.run(main.create_discovery_job(payload))


def test_job_creation_binds_configured_tenant_when_quota_enabled(monkeypatch) -> None:
    monkeypatch.setattr(main, "load_quota_policy", lambda: QuotaPolicy(
        enabled=True,
        hourly_run_limit=10,
        daily_run_limit=10,
        hourly_job_limit=10,
        daily_job_limit=10,
    ))
    monkeypatch.setenv("SALVA_TENANT_ID", "tenant-bound")

    captured = {}

    def fake_create_job(discovery, meta=None):
        captured["tenant_id"] = discovery.tenant_id
        return "job:demo"

    monkeypatch.setattr(main, "create_job", fake_create_job)
    monkeypatch.setattr(main, "run_job", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        main,
        "get_job",
        lambda job_id: JobRecord(
            job_id=job_id,
            status="completed",
            objective="find_leads",
            output_profile="lead",
            tenant_id="tenant-bound",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            request={"tenant_id": "tenant-bound"},
            run_id="run:demo",
            error=None,
            meta={"tenant_id": "tenant-bound"},
        ),
    )

    payload = JobCreateRequest(
        discovery=DiscoveryRequest(
            objective="find_leads",
            intent=DiscoveryIntent(market="Germany", industry="software"),
        )
    )

    item = asyncio.run(main.create_discovery_job(payload))

    assert item.tenant_id == "tenant-bound"
    assert captured["tenant_id"] == "tenant-bound"


def test_usage_and_quota_endpoints_bind_configured_tenant_when_quota_enabled(monkeypatch) -> None:
    monkeypatch.setattr(main, "load_quota_policy", lambda: QuotaPolicy(
        enabled=True,
        hourly_run_limit=10,
        daily_run_limit=10,
        hourly_job_limit=10,
        daily_job_limit=10,
    ))
    monkeypatch.setenv("SALVA_TENANT_ID", "tenant-bound")

    client = TestClient(main.app)

    usage_response = client.get("/v1/usage")
    quota_response = client.get("/v1/quota")

    assert usage_response.status_code == 200
    assert quota_response.status_code == 200
    assert usage_response.json()["tenant_id"] == "tenant-bound"
    assert quota_response.json()["tenant_id"] == "tenant-bound"


def test_usage_and_quota_endpoints_reject_mismatched_tenant_when_quota_enabled(monkeypatch) -> None:
    monkeypatch.setattr(main, "load_quota_policy", lambda: QuotaPolicy(
        enabled=True,
        hourly_run_limit=10,
        daily_run_limit=10,
        hourly_job_limit=10,
        daily_job_limit=10,
    ))
    monkeypatch.setenv("SALVA_TENANT_ID", "tenant-bound")

    client = TestClient(main.app)

    usage_response = client.get("/v1/usage", params={"tenant_id": "tenant-other"})
    quota_response = client.get("/v1/quota", params={"tenant_id": "tenant-other"})

    assert usage_response.status_code == 403
    assert quota_response.status_code == 403
