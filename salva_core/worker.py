from __future__ import annotations

import socket
import time
from typing import Any

from salva_core import service
from salva_core.persistence import (
    DEFAULT_DB_PATH,
    append_stream_event,
    claim_next_job,
    get_job,
    get_job_request,
    persist_discovery_run,
    update_run_meta,
    update_job_status,
)
from salva_core.transforms import transform_entities


def default_worker_id() -> str:
    return f"worker:{socket.gethostname()}"


def run_job(job_id: str, path: str | None = None, execution_mode: str = "worker") -> dict[str, Any]:
    db_path = path or DEFAULT_DB_PATH
    request = get_job_request(job_id, path=db_path)
    if request is None:
        raise KeyError(f"job not found: {job_id}")

    update_job_status(
        job_id,
        "running",
        meta={"execution_mode": execution_mode},
        path=db_path,
    )
    append_stream_event(
        job_id,
        "job_started",
        "工作開始執行 discovery。",
        {"execution_mode": execution_mode},
        path=db_path,
    )

    try:
        entities, relations, telemetry, meta, source_attempts = service.execute_discovery(request)
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
        item = get_job(job_id, path=db_path)
        return {
            "job_id": job_id,
            "run_id": run_id,
            "status": "completed",
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
