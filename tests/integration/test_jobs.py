import asyncio
from datetime import UTC, datetime, timedelta

import pytest

import salva_core.worker as worker
from apps.api.main import create_discovery_job, job_cancel, job_detail, job_events
from salva_core.persistence import (
    create_job,
    get_job,
    is_cancel_requested,
    list_jobs,
    list_stream_events,
    request_cancellation,
    touch_job_heartbeat,
    update_job_status,
)
from salva_core.persistence.db import get_conn
from salva_core.schemas import DiscoveryIntent, DiscoveryRequest, JobCreateRequest
from salva_core.worker import JobCancelled, run_job, run_next_job


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
        cancel_job as persistence_cancel_job,
    )
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
    api_main.cancel_job = lambda job_id, force=False: persistence_cancel_job(
        job_id,
        force=force,
        path=db_path,
    )


# ---------------------------------------------------------------------------
# Cancellation: cancel_requested flag + round_checkpoint interruption, and
# the update_job_status guard that stops a late completion/failure write
# from resurrecting an already-cancelled job.
# ---------------------------------------------------------------------------


def _make_request(tenant_id: str = "tenant-cancel") -> DiscoveryRequest:
    return DiscoveryRequest(
        objective="find_leads",
        tenant_id=tenant_id,
        intent=DiscoveryIntent(market="Germany", industry="software"),
        execution={"persistence": "none"},
    )


def test_update_job_status_does_not_overwrite_cancelled_with_completed_or_failed(tmp_path) -> None:
    db_path = str(tmp_path / "salva-cancel-race.db")
    job_id = create_job(_make_request(), path=db_path)
    update_job_status(job_id, "running", path=db_path)
    request_cancellation(job_id, path=db_path)
    assert is_cancel_requested(job_id, path=db_path)

    # Worker observes the flag at a round_checkpoint and finalizes as cancelled.
    update_job_status(job_id, "cancelled", meta={"cancelled_at": "now"}, path=db_path)

    # A "late" write from execution that was still in flight and never saw
    # the cancel flag in time -- must not resurrect the job.
    update_job_status(job_id, "completed", run_id="run:late", path=db_path)
    job = get_job(job_id, path=db_path)
    assert job.status == "cancelled"
    assert job.run_id is None

    update_job_status(job_id, "failed", error="late failure", path=db_path)
    job = get_job(job_id, path=db_path)
    assert job.status == "cancelled"
    assert job.error is None


def test_run_job_stops_at_round_checkpoint_when_cancel_requested(monkeypatch, tmp_path) -> None:
    db_path = str(tmp_path / "salva-cancel-worker.db")
    job_id = create_job(_make_request(), path=db_path)
    update_job_status(job_id, "running", path=db_path)

    def fake_execute_discovery(payload, round_checkpoint=None):
        # Simulate a cancel arriving mid-run; the controller's round loop
        # calls round_checkpoint() between rounds and observes it.
        request_cancellation(job_id, path=db_path)
        assert round_checkpoint is not None
        round_checkpoint()
        raise AssertionError("unreachable: round_checkpoint should have raised JobCancelled")

    monkeypatch.setattr(worker.service, "execute_discovery", fake_execute_discovery)

    result = run_job(job_id, path=db_path, execution_mode="worker")

    assert result["status"] == "cancelled"
    job = get_job(job_id, path=db_path)
    assert job.status == "cancelled"
    assert job.run_id is None
    events, _ = list_stream_events(job_id=job_id, path=db_path)
    assert any(e.event_type == "job_cancelled" for e in events)
    assert not any(e.event_type in ("job_completed", "job_failed") for e in events)


def test_round_checkpoint_raises_job_cancelled_when_flagged(tmp_path) -> None:
    db_path = str(tmp_path / "salva-cancel-checkpoint.db")
    job_id = create_job(_make_request(), path=db_path)
    update_job_status(job_id, "running", path=db_path)
    checkpoint = worker._make_round_checkpoint(job_id, db_path)

    checkpoint()  # no cancel requested yet -- must not raise

    request_cancellation(job_id, path=db_path)
    with pytest.raises(JobCancelled):
        checkpoint()


def test_run_job_defers_to_cancelled_status_written_during_tail(monkeypatch, tmp_path) -> None:
    db_path = str(tmp_path / "salva-cancel-tail.db")
    job_id = create_job(_make_request(), path=db_path)
    update_job_status(job_id, "running", path=db_path)

    def fake_execute_discovery(payload, round_checkpoint=None):
        # Cancel gets finalized to "cancelled" (e.g. by another checkpoint
        # firing concurrently) after the last checkpoint but before this
        # call returns -- the tail-of-run race the audit flagged.
        update_job_status(job_id, "cancelled", meta={"cancelled_at": "now"}, path=db_path)
        return [], [], [], {}, []

    monkeypatch.setattr(worker.service, "execute_discovery", fake_execute_discovery)

    result = run_job(job_id, path=db_path, execution_mode="worker")

    assert result["status"] == "cancelled"
    job = get_job(job_id, path=db_path)
    assert job.status == "cancelled"
    assert job.run_id is None
    events, _ = list_stream_events(job_id=job_id, path=db_path)
    assert not any(e.event_type == "job_completed" for e in events)


# ---------------------------------------------------------------------------
# Heartbeat + passive orphan (worker-crash) recovery
# ---------------------------------------------------------------------------


def test_get_job_reaps_running_job_with_stale_heartbeat(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SALVA_JOB_HEARTBEAT_TIMEOUT_SECONDS", "60")
    db_path = str(tmp_path / "salva-orphan.db")
    job_id = create_job(_make_request(), path=db_path)
    update_job_status(job_id, "running", path=db_path)
    touch_job_heartbeat(job_id, path=db_path)

    stale = (datetime.now(UTC) - timedelta(seconds=120)).isoformat()
    with get_conn(db_path) as conn:
        conn.execute("UPDATE jobs SET heartbeat_at = ? WHERE job_id = ?", (stale, job_id))

    job = get_job(job_id, path=db_path)
    assert job.status == "failed"
    assert job.error is not None
    assert "heartbeat" in job.error.lower()


def test_get_job_does_not_reap_running_job_with_fresh_heartbeat(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SALVA_JOB_HEARTBEAT_TIMEOUT_SECONDS", "300")
    db_path = str(tmp_path / "salva-fresh-heartbeat.db")
    job_id = create_job(_make_request(), path=db_path)
    update_job_status(job_id, "running", path=db_path)
    touch_job_heartbeat(job_id, path=db_path)

    job = get_job(job_id, path=db_path)
    assert job.status == "running"
    assert job.heartbeat_at is not None


def test_get_job_does_not_reap_running_job_with_no_heartbeat_yet(tmp_path, monkeypatch) -> None:
    # A job that just transitioned to "running" and hasn't hit its first
    # round_checkpoint yet has no heartbeat -- must not be reaped instantly.
    monkeypatch.setenv("SALVA_JOB_HEARTBEAT_TIMEOUT_SECONDS", "1")
    db_path = str(tmp_path / "salva-no-heartbeat.db")
    job_id = create_job(_make_request(), path=db_path)
    update_job_status(job_id, "running", path=db_path)

    job = get_job(job_id, path=db_path)
    assert job.status == "running"


# ---------------------------------------------------------------------------
# REST /v1/jobs/{job_id}/cancel
# ---------------------------------------------------------------------------


def test_rest_cancel_endpoint_cancels_queued_job() -> None:
    db_path = "/private/tmp/salva-test-rest-cancel-queued.db"
    _isolate_job_runtime(db_path)
    payload = JobCreateRequest(
        discovery=DiscoveryRequest(
            objective="find_leads",
            tenant_id="tenant-rest-cancel",
            intent=DiscoveryIntent(market="Germany", industry="software"),
        ),
        wait_for_completion=False,
    )
    item = asyncio.run(create_discovery_job(payload))
    assert item.status == "queued"

    cancelled = asyncio.run(job_cancel(item.job_id))
    assert cancelled.status == "cancelled"


def test_rest_cancel_endpoint_running_job_requires_force() -> None:
    db_path = "/private/tmp/salva-test-rest-cancel-running.db"
    _isolate_job_runtime(db_path)
    payload = JobCreateRequest(
        discovery=DiscoveryRequest(
            objective="find_leads",
            tenant_id="tenant-rest-cancel-running",
            intent=DiscoveryIntent(market="Germany", industry="software"),
        ),
        wait_for_completion=False,
    )
    item = asyncio.run(create_discovery_job(payload))
    update_job_status(item.job_id, "running", path=db_path)

    with pytest.raises(Exception) as excinfo:
        asyncio.run(job_cancel(item.job_id))
    err = str(excinfo.value).lower()
    assert "force" in err or getattr(excinfo.value, "status_code", None) == 409

    cancelled = asyncio.run(job_cancel(item.job_id, force=True))
    assert cancelled.status == "running"  # cooperative cancel: flag set, not yet stopped
    assert is_cancel_requested(item.job_id, path=db_path)


def test_rest_cancel_endpoint_unknown_job_404() -> None:
    db_path = "/private/tmp/salva-test-rest-cancel-unknown.db"
    _isolate_job_runtime(db_path)

    with pytest.raises(Exception) as excinfo:
        asyncio.run(job_cancel("job:does-not-exist"))
    assert getattr(excinfo.value, "status_code", None) == 404
