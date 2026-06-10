"""Job queue and stream event persistence."""
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

from salva_core.schemas import DiscoveryRequest, JobRecord, StreamEventRecord

from .db import DEFAULT_DB_PATH, get_conn


def create_job(
    request: DiscoveryRequest,
    meta: dict | None = None,
    path: str = DEFAULT_DB_PATH,
) -> str:
    job_id = f"job:{uuid.uuid4()}"
    now = datetime.now(UTC).isoformat()
    meta_payload = dict(meta or {})
    if request.tenant_id is not None:
        meta_payload.setdefault("tenant_id", request.tenant_id)
    project_id = request.execution.project_id if request.execution else None
    with get_conn(path) as conn:
        conn.execute(
            """
            INSERT INTO jobs (
                job_id, status, objective, output_profile, project_id, tenant_id,
                request_json, run_id, error, meta_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                "queued",
                request.objective,
                request.output_profile,
                project_id,
                request.tenant_id,
                request.model_dump_json(),
                None,
                None,
                json.dumps(meta_payload, ensure_ascii=False),
                now,
                now,
            ),
        )
    append_stream_event(job_id, "job_queued", "工作已建立，等待執行。", meta_payload, path=path)
    return job_id


def update_job_status(
    job_id: str,
    status: str,
    run_id: str | None = None,
    error: str | None = None,
    meta: dict | None = None,
    path: str = DEFAULT_DB_PATH,
) -> None:
    now = datetime.now(UTC).isoformat()
    with get_conn(path) as conn:
        existing = conn.execute(
            "SELECT meta_json, run_id, error, tenant_id FROM jobs WHERE job_id = ?",
            (job_id,),
        ).fetchone()
        if existing is None:
            raise KeyError(f"job not found: {job_id}")

        existing_meta = json.loads(existing[0]) if existing[0] else {}
        if meta:
            existing_meta.update(meta)
        tenant_id = existing[3]
        if tenant_id is None:
            candidate = existing_meta.get("tenant_id")
            if isinstance(candidate, str) and candidate.strip():
                tenant_id = candidate.strip()

        conn.execute(
            """
            UPDATE jobs
            SET status = ?, run_id = ?, error = ?, tenant_id = ?, meta_json = ?, updated_at = ?
            WHERE job_id = ?
            """,
            (
                status,
                run_id if run_id is not None else existing[1],
                error if error is not None else existing[2],
                tenant_id,
                json.dumps(existing_meta, ensure_ascii=False),
                now,
                job_id,
            ),
        )


def append_stream_event(
    job_id: str,
    event_type: str,
    message: str,
    data: dict | None = None,
    path: str = DEFAULT_DB_PATH,
) -> None:
    now = datetime.now(UTC).isoformat()
    with get_conn(path) as conn:
        conn.execute(
            """
            INSERT INTO stream_events (
                event_id, job_id, event_type, message, data_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                f"event:{uuid.uuid4()}",
                job_id,
                event_type,
                message,
                json.dumps(data or {}, ensure_ascii=False),
                now,
            ),
        )


def list_jobs(
    limit: int = 20,
    offset: int = 0,
    status: str | None = None,
    project_id: str | None = None,
    path: str = DEFAULT_DB_PATH,
) -> tuple[list[JobRecord], int]:
    clauses: list[str] = []
    params: list[object] = []
    if status:
        clauses.append("status = ?")
        params.append(status)
    if project_id:
        clauses.append("project_id = ?")
        params.append(project_id)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    with get_conn(path) as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM jobs {where}",
            params,
        ).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT job_id, status, objective, output_profile, project_id, tenant_id,
                   request_json, run_id, error, meta_json, created_at, updated_at
            FROM jobs
            {where}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        ).fetchall()

    items = [
        JobRecord(
            job_id=row[0],
            status=row[1],
            objective=row[2],
            output_profile=row[3],
            project_id=row[4],
            tenant_id=row[5],
            request=json.loads(row[6]),
            run_id=row[7],
            error=row[8],
            meta=json.loads(row[9]),
            created_at=datetime.fromisoformat(row[10]),
            updated_at=datetime.fromisoformat(row[11]),
        )
        for row in rows
    ]
    return items, int(total)


def get_job(job_id: str, path: str = DEFAULT_DB_PATH) -> JobRecord | None:
    with get_conn(path) as conn:
        row = conn.execute(
            """
            SELECT job_id, status, objective, output_profile, project_id, tenant_id,
                   request_json, run_id, error, meta_json, created_at, updated_at
            FROM jobs
            WHERE job_id = ?
            """,
            (job_id,),
        ).fetchone()

    if row is None:
        return None

    return JobRecord(
        job_id=row[0],
        status=row[1],
        objective=row[2],
        output_profile=row[3],
        project_id=row[4],
        tenant_id=row[5],
        request=json.loads(row[6]),
        run_id=row[7],
        error=row[8],
        meta=json.loads(row[9]),
        created_at=datetime.fromisoformat(row[10]),
        updated_at=datetime.fromisoformat(row[11]),
    )


def get_job_request(job_id: str, path: str = DEFAULT_DB_PATH) -> DiscoveryRequest | None:
    with get_conn(path) as conn:
        row = conn.execute(
            "SELECT request_json FROM jobs WHERE job_id = ?",
            (job_id,),
        ).fetchone()

    if row is None:
        return None

    return DiscoveryRequest.model_validate_json(row[0])


def claim_next_job(worker_id: str, path: str = DEFAULT_DB_PATH) -> JobRecord | None:
    now = datetime.now(UTC).isoformat()
    with get_conn(path) as conn:
        row = conn.execute(
            """
            SELECT job_id
            FROM jobs
            WHERE status = 'queued'
            ORDER BY created_at ASC
            LIMIT 1
            """
        ).fetchone()

        if row is None:
            return None

        job_id = row[0]
        conn.execute(
            """
            UPDATE jobs
            SET status = ?, worker_id = ?, updated_at = ?
            WHERE job_id = ? AND status = 'queued'
            """,
            ("running", worker_id, now, job_id),
        )
        updated = conn.execute("SELECT changes()").fetchone()[0]

    if updated == 0:
        return None

    return get_job(job_id, path=path)


def list_stream_events(
    job_id: str,
    limit: int = 200,
    offset: int = 0,
    path: str = DEFAULT_DB_PATH,
) -> tuple[list[StreamEventRecord], int]:
    with get_conn(path) as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM stream_events WHERE job_id = ?",
            (job_id,),
        ).fetchone()[0]
        rows = conn.execute(
            """
            SELECT job_id, event_type, message, created_at, data_json
            FROM stream_events
            WHERE job_id = ?
            ORDER BY created_at ASC
            LIMIT ? OFFSET ?
            """,
            (job_id, limit, offset),
        ).fetchall()

    items = [
        StreamEventRecord(
            job_id=row[0],
            event_type=row[1],
            message=row[2],
            created_at=datetime.fromisoformat(row[3]),
            data=json.loads(row[4]),
        )
        for row in rows
    ]
    return items, int(total)
