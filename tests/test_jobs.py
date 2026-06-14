import asyncio

import pytest

import salva_core.worker as worker
from apps.api.main import create_discovery_job, job_detail, job_events
from salva_core.persistence import (
    create_job,
    get_job,
    list_jobs,
    list_stream_events,
    update_job_status,
)
from salva_core.schemas import DiscoveryIntent, DiscoveryRequest, JobCreateRequest
from salva_core.worker import run_next_job


def test_job_persistence_roundtrip(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "salva_jobs.db")
    monkeypatch.setenv("SALVA_SQLITE_PATH", db_path)

    request = DiscoveryRequest(
        objective="find_leads",
        tenant_id="tenant-roundtrip",
        intent=DiscoveryIntent(market="Germany", industry="software"),
    )
    job_id = create_job(request, path=db_path)
    update_job_status(job_id, "completed", run_id="run:test", meta={"qualified_count": 0}, path=db_path)

    job = get_job(job_id, path=db_path)
    items, total = list_jobs(path=db_path)
    events, event_total = list_stream_events(job_id=job_id, path=db_path)

    assert job is not None
    assert job.run_id == "run:test"
    assert job.status == "completed"
    assert job.tenant_id == "tenant-roundtrip"
    assert job.meta["tenant_id"] == "tenant-roundtrip"
    assert total == 1
    assert items[0].job_id == job_id
    assert items[0].tenant_id == "tenant-roundtrip"
    assert event_total >= 1
    assert events[0].event_type == "job_queued"


def test_job_api_inline_execution() -> None:
    db_path = "/private/tmp/salva-test-inline.db"
    _isolate_job_runtime(db_path)
    payload = JobCreateRequest(
        discovery=DiscoveryRequest(
            objective="find_events",
            tenant_id="tenant-inline",
            intent=DiscoveryIntent(market="Taipei", industry="design"),
            max_results=5,
        )
    )
    item = asyncio.run(create_discovery_job(payload))
    detail = asyncio.run(job_detail(item.job_id))
    events = asyncio.run(job_events(item.job_id))

    assert item.status == "completed"
    assert item.run_id is not None
    assert detail.job_id == item.job_id
    assert detail.tenant_id == "tenant-inline"
    assert "feedback" in detail.meta
    assert events.total >= 3


def test_job_queue_then_worker_execution() -> None:
    db_path = "/private/tmp/salva-test-worker.db"
    _isolate_job_runtime(db_path)
    payload = JobCreateRequest(
        discovery=DiscoveryRequest(
            objective="find_leads",
            tenant_id="tenant-worker",
            intent=DiscoveryIntent(market="Germany", industry="software", product="crm"),
            max_results=3,
        ),
        wait_for_completion=False,
    )
    item = asyncio.run(create_discovery_job(payload))
    assert item.status == "queued"
    assert item.run_id is None
    assert item.tenant_id == "tenant-worker"

    result = run_next_job(worker_id="worker:test")
    assert result is not None
    assert result["job_id"] == item.job_id

    detail = asyncio.run(job_detail(item.job_id))
    events = asyncio.run(job_events(item.job_id))
    assert detail.status == "completed"
    assert detail.run_id is not None
    assert detail.tenant_id == "tenant-worker"
    assert "feedback" in detail.meta
    assert any(event.event_type == "job_completed" for event in events.items)


def test_default_worker_id_uses_hostname(monkeypatch) -> None:
    monkeypatch.setattr(worker.socket, "gethostname", lambda: "salva-test-node")
    assert worker.default_worker_id() == "worker:salva-test-node"


def test_run_job_missing_job_raises_key_error(monkeypatch) -> None:
    monkeypatch.setattr(worker, "get_job_request", lambda job_id, path=None: None)

    with pytest.raises(KeyError, match="job not found"):
        worker.run_job("job:missing", path="/private/tmp/salva-missing.db")


def test_run_next_job_returns_none_when_queue_empty(monkeypatch) -> None:
    monkeypatch.setattr(worker, "claim_next_job", lambda resolved_worker_id, path=None: None)

    assert worker.run_next_job(worker_id="worker:test", path="/private/tmp/salva-empty.db") is None


def test_run_worker_loop_once_returns_zero_on_empty_queue(monkeypatch) -> None:
    monkeypatch.setattr(worker, "run_next_job", lambda worker_id=None, path=None: None)

    assert worker.run_worker_loop(worker_id="worker:test", once=True, path="/private/tmp/salva-empty.db") == 0


def test_run_worker_loop_once_counts_single_job(monkeypatch) -> None:
    calls: list[str] = []

    def fake_run_next_job(worker_id=None, path=None):  # noqa: ANN001
        calls.append(str(worker_id))
        return {"job_id": "job:demo"}

    monkeypatch.setattr(worker, "run_next_job", fake_run_next_job)

    assert worker.run_worker_loop(worker_id="worker:test", once=True, path="/private/tmp/salva-once.db") == 1
    assert calls == ["worker:test"]


def _isolate_job_runtime(db_path: str) -> None:
    import apps.api.main as api_main
    import salva_core.worker as worker
    from salva_core.persistence import (
        create_job as persistence_create_job,
    )
    from salva_core.persistence import (
        get_job as persistence_get_job,
    )
    from salva_core.persistence import (
        list_jobs as persistence_list_jobs,
    )
    from salva_core.persistence import (
        list_stream_events as persistence_list_stream_events,
    )
    from salva_core.worker import run_job as worker_run_job

    # Fresh local DB for each job-related test.
    worker.DEFAULT_DB_PATH = db_path

    api_main.create_job = lambda request, meta=None: persistence_create_job(request, meta=meta, path=db_path)
    api_main.run_job = lambda job_id, execution_mode="inline": worker_run_job(
        job_id,
        path=db_path,
        execution_mode=execution_mode,
    )
    api_main.get_job = lambda job_id: persistence_get_job(job_id, path=db_path)
    api_main.list_jobs = lambda limit=20, offset=0, status=None: persistence_list_jobs(
        limit=limit,
        offset=offset,
        status=status,
        path=db_path,
    )
    api_main.list_stream_events = lambda job_id, limit=200, offset=0: persistence_list_stream_events(
        job_id=job_id,
        limit=limit,
        offset=offset,
        path=db_path,
    )
