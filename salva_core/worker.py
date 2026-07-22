from __future__ import annotations

import socket
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from salva_core import service
from salva_core.execution import resolve_execution_request
from salva_core.persistence import (
    DEFAULT_DB_PATH,
    append_stream_event,
    claim_next_job,
    get_job,
    get_job_request,
    is_cancel_requested,
    persist_discovery_run,
    touch_job_heartbeat,
    update_job_status,
    update_run_meta,
)
from salva_core.transforms import transform_entities


class JobCancelled(Exception):
    """Raised by the round_checkpoint callback when a cancel was observed mid-run."""


def default_worker_id() -> str:
    return f"worker:{socket.gethostname()}"


def _make_round_checkpoint(job_id: str, db_path: str) -> Callable[[], None]:
    def _checkpoint() -> None:
        touch_job_heartbeat(job_id, path=db_path)
        if is_cancel_requested(job_id, path=db_path):
            raise JobCancelled(job_id)

    return _checkpoint


def run_job(job_id: str, path: str | None = None, execution_mode: str = "worker") -> dict[str, Any]:
    db_path = path or DEFAULT_DB_PATH
    request = get_job_request(job_id, path=db_path)
    if request is None:
        raise KeyError(f"job not found: {job_id}")
    request = resolve_execution_request(request)

    update_job_status(
        job_id,
        "running",
        meta={"execution_mode": execution_mode},
        path=db_path,
    )
    touch_job_heartbeat(job_id, path=db_path)
    append_stream_event(
        job_id,
        "job_started",
        "工作開始執行 discovery。",
        {"execution_mode": execution_mode},
        path=db_path,
    )

    round_checkpoint = _make_round_checkpoint(job_id, db_path)

    try:
        entities, relations, telemetry, meta, source_attempts = service.execute_discovery(
            request, round_checkpoint=round_checkpoint,
        )
        run_id: str | None = None
        feedback: dict[str, Any] = {}
        if request.execution.persistence == "audit":
            run_id = persist_discovery_run(
                request,
                entities,
                relations,
                telemetry,
                meta,
                source_attempts=source_attempts,
                path=db_path,
            )
            feedback = service.build_request_feedback(run_id, request, path=db_path)
            update_run_meta(run_id, {"feedback": feedback}, path=db_path)
        transformed_items = transform_entities(
            entities,
            request.output_profile,
            request.transform,
        )
        final_meta = {
            **meta,
            "run_id": run_id,
            "feedback": feedback,
            "transformed_count": len(transformed_items),
            "execution_mode": execution_mode,
        }
        if request.tenant_id is not None:
            final_meta.setdefault("tenant_id", request.tenant_id)
        update_job_status(
            job_id,
            "completed",
            run_id=run_id,
            meta=final_meta,
            path=db_path,
        )
        item = get_job(job_id, path=db_path)
        if item is not None and item.status == "cancelled":
            # Cancel was requested after the last round_checkpoint observed it
            # (i.e. during the tail of this run) -- update_job_status's guard
            # already suppressed the "completed" write above; keep the event
            # stream and return value consistent with that, not stale.
            append_stream_event(
                job_id,
                "job_cancelled",
                "工作已取消（完成前偵測到取消請求，結果未寫入）。",
                {},
                path=db_path,
            )
            return {
                "job_id": job_id,
                "run_id": item.run_id,
                "status": "cancelled",
                "job": item.model_dump(mode="json"),
            }
        if run_id is not None:
            append_stream_event(
                job_id,
                "run_persisted",
                "Discovery run 已寫入持久化儲存。",
                {"run_id": run_id},
                path=db_path,
            )
        append_stream_event(
            job_id,
            "job_completed",
            "工作執行完成。",
            {
                "run_id": run_id,
                "entity_count": len(entities),
                "relation_count": len(relations),
                "telemetry_count": len(telemetry),
                "transformed_count": len(transformed_items),
            },
            path=db_path,
        )
        return {
            "job_id": job_id,
            "run_id": run_id,
            "status": "completed",
            "job": item.model_dump(mode="json") if item else None,
        }
    except JobCancelled:
        update_job_status(
            job_id,
            "cancelled",
            meta={"execution_mode": execution_mode, "cancelled_at": datetime.now(UTC).isoformat()},
            path=db_path,
        )
        append_stream_event(
            job_id,
            "job_cancelled",
            "工作於執行中偵測到取消請求，已中止。",
            {},
            path=db_path,
        )
        item = get_job(job_id, path=db_path)
        return {
            "job_id": job_id,
            "run_id": None,
            "status": "cancelled",
            "job": item.model_dump(mode="json") if item else None,
        }
    except Exception as exc:
        update_job_status(
            job_id,
            "failed",
            error=str(exc),
            meta={"execution_mode": execution_mode},
            path=db_path,
        )
        item = get_job(job_id, path=db_path)
        if item is not None and item.status == "cancelled":
            # Same race as the success path above -- cancellation wins,
            # the "failed" write was suppressed; don't emit job_failed.
            append_stream_event(
                job_id,
                "job_cancelled",
                "工作已取消（執行拋出例外前偵測到取消請求）。",
                {},
                path=db_path,
            )
            return {
                "job_id": job_id,
                "run_id": None,
                "status": "cancelled",
                "job": item.model_dump(mode="json"),
            }
        append_stream_event(
            job_id,
            "job_failed",
            "工作執行失敗。",
            {"error": str(exc)},
            path=db_path,
        )
        raise


def run_next_job(worker_id: str | None = None, path: str | None = None) -> dict[str, Any] | None:
    resolved_worker_id = worker_id or default_worker_id()
    db_path = path or DEFAULT_DB_PATH
    claimed = claim_next_job(resolved_worker_id, path=db_path)
    if claimed is None:
        return None
    return run_job(claimed.job_id, path=db_path, execution_mode="worker")


def run_worker_loop(
    worker_id: str | None = None,
    poll_interval: float = 2.0,
    once: bool = False,
    path: str | None = None,
) -> int:
    resolved_worker_id = worker_id or default_worker_id()
    processed = 0
    while True:
        result = run_next_job(worker_id=resolved_worker_id, path=path)
        if result is not None:
            processed += 1
        elif once:
            return processed

        if once and result is not None:
            return processed

        time.sleep(poll_interval)
