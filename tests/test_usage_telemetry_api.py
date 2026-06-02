import asyncio

from fastapi.testclient import TestClient

from apps.api import main
from salva_core.persistence import (
    create_job,
    get_job,
    list_usage_telemetry,
    persist_discovery_run,
    update_job_status,
)
from salva_core.schemas import DiscoveryIntent, DiscoveryRequest


def test_tenant_id_propagates_into_discovery_response(monkeypatch) -> None:
    payload = DiscoveryRequest(
        objective="find_companies",
        tenant_id="tenant-acme",
        intent=DiscoveryIntent(market="US", industry="software"),
        max_results=3,
    )

    monkeypatch.setattr(
        main.service,
        "run_discovery",
        lambda discovery: ([], [], [], {"tenant_id": discovery.tenant_id}),
    )
    result = asyncio.run(main.discover(payload))

    assert result.meta["tenant_id"] == "tenant-acme"


def test_job_creation_keeps_tenant_id_in_meta(tmp_path) -> None:
    db_path = str(tmp_path / "salva_usage.db")
    request = DiscoveryRequest(
        objective="find_leads",
        tenant_id="tenant-beta",
        intent=DiscoveryIntent(market="Germany", industry="software", product="crm"),
    )

    job_id = create_job(request, path=db_path)
    update_job_status(job_id, "queued", path=db_path)

    job = get_job(job_id, path=db_path)
    assert job is not None
    assert job.meta["tenant_id"] == "tenant-beta"


def test_usage_telemetry_api_aggregates_by_tenant(tmp_path) -> None:
    db_path = str(tmp_path / "salva_usage.db")
    _isolate_usage_runtime(db_path)

    tenant_a = DiscoveryRequest(
        objective="find_leads",
        tenant_id="tenant-a",
        intent=DiscoveryIntent(market="Germany", industry="software", product="crm"),
    )
    tenant_b = DiscoveryRequest(
        objective="find_events",
        tenant_id="tenant-b",
        intent=DiscoveryIntent(market="Taipei", industry="design"),
    )

    run_a = persist_discovery_run(
        request=tenant_a,
        entities=[],
        relations=[],
        telemetry=[],
        meta={"qualified_count": 3, "raw_count": 10, "provider_kinds": []},
        source_attempts=[],
        path=db_path,
    )
    run_b = persist_discovery_run(
        request=tenant_b,
        entities=[],
        relations=[],
        telemetry=[],
        meta={"qualified_count": 1, "raw_count": 4, "provider_kinds": []},
        source_attempts=[],
        path=db_path,
    )

    job_a = create_job(tenant_a, path=db_path)
    update_job_status(job_a, "completed", run_id=run_a, path=db_path)
    job_b = create_job(tenant_b, path=db_path)
    update_job_status(job_b, "failed", run_id=run_b, path=db_path)

    usage = list_usage_telemetry(path=db_path)
    assert usage.total_tenants == 2
    assert usage.total_runs == 2
    assert usage.total_jobs == 2
    tenant_ids = {item.tenant_id for item in usage.items}
    assert tenant_ids == {"tenant-a", "tenant-b"}

    client = TestClient(main.app)
    response = client.get("/v1/usage", params={"tenant_id": "tenant-a"})
    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == "tenant-a"
    assert body["total_tenants"] == 1
    assert body["items"][0]["tenant_id"] == "tenant-a"
    assert body["items"][0]["run_count"] == 1
    assert body["items"][0]["job_count"] == 1


def _isolate_usage_runtime(db_path: str) -> None:
    import apps.api.main as api_main
    from salva_core.persistence import list_usage_telemetry as persistence_list_usage_telemetry

    api_main.list_usage_telemetry = lambda tenant_id=None: persistence_list_usage_telemetry(
        tenant_id=tenant_id,
        path=db_path,
    )
