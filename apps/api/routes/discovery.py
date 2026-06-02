"""
Discovery API routes: /v1/discover, /v1/jobs
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from typing import Annotated, AsyncGenerator

from salva_core import service
from salva_core.schemas import (
    DiscoveryRequest,
    DiscoveryResponse,
    JobCreateRequest,
    JobRecord,
    JobsResponse,
    StreamEventsResponse,
)
from salva_core.quotas import evaluate_tenant_quota
from salva_core.worker import run_job
from apps.api.dependencies import resolve_tenant_scope, ensure_quota_allowed

router = APIRouter()


@router.post("/discover", response_model=DiscoveryResponse)
async def discover(payload: DiscoveryRequest) -> DiscoveryResponse:
    """Synchronous discovery endpoint - returns results directly"""
    tenant_id = resolve_tenant_scope(payload.tenant_id, "discover")
    payload = payload.model_copy(update={"tenant_id": tenant_id})
    quota = evaluate_tenant_quota(tenant_id)
    ensure_quota_allowed(quota, "discover")
    
    entities, relations, telemetry, meta = service.run_discovery(payload)
    
    from salva_core.transforms import transform_entities
    transformed_items = transform_entities(entities, payload.output_profile, payload.transform)
    
    return DiscoveryResponse(
        objective=payload.objective,
        output_profile=payload.output_profile,
        entities=entities,
        transformed_items=transformed_items,
        relations=relations,
        telemetry=telemetry,
        meta=meta,
    )


@router.post("/jobs", response_model=JobRecord)
async def create_discovery_job(payload: JobCreateRequest) -> JobRecord:
    """Asynchronous job creation endpoint"""
    from salva_core.persistence import create_job, get_job
    
    discovery = payload.discovery
    tenant_id = resolve_tenant_scope(discovery.tenant_id, "job")
    discovery = discovery.model_copy(update={"tenant_id": tenant_id})
    
    quota = evaluate_tenant_quota(tenant_id)
    ensure_quota_allowed(quota, "job")
    
    job_id = create_job(
        discovery,
        meta={"wait_for_completion": payload.wait_for_completion},
    )

    if not payload.wait_for_completion:
        item = get_job(job_id)
        if item is None:
            raise HTTPException(status_code=500, detail="Job created but cannot be loaded")
        return item

    try:
        run_job(job_id, execution_mode="inline")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Job execution failed: {exc}") from exc

    item = get_job(job_id)
    if item is None:
        raise HTTPException(status_code=500, detail="Job completed but cannot be loaded")
    return item


@router.get("/jobs", response_model=JobsResponse)
async def jobs(
    status: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> JobsResponse:
    """List all jobs"""
    from salva_core.persistence import list_jobs
    from salva_core.schemas import JobsResponse
    
    items, total = list_jobs(status=status, limit=limit, offset=offset)
    return JobsResponse(items=items, total=total)


@router.get("/jobs/{job_id}", response_model=JobRecord)
async def job_detail(job_id: str) -> JobRecord:
    """Get job details"""
    from salva_core.persistence import get_job
    
    item = get_job(job_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return item


@router.get("/jobs/{job_id}/events", response_model=StreamEventsResponse)
async def job_events(
    job_id: str,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> StreamEventsResponse:
    """Get job events"""
    from salva_core.persistence import get_job, list_stream_events
    from salva_core.schemas import StreamEventsResponse
    
    item = get_job(job_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Job not found")
    
    items, total = list_stream_events(job_id=job_id, limit=limit, offset=offset)
    return StreamEventsResponse(items=items, total=total)


@router.get("/jobs/{job_id}/stream")
async def job_stream(job_id: str) -> StreamingResponse:
    """SSE stream for job status"""
    import json
    import asyncio
    from fastapi.responses import StreamingResponse
    from salva_core.persistence import get_job, list_stream_events
    
    item = get_job(job_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Job not found")

    TERMINAL_JOB_STATUSES = {"completed", "failed"}

    async def event_generator() -> AsyncGenerator[str, None]:
        sent = 0
        while True:
            events, total = list_stream_events(job_id=job_id, limit=500, offset=0)
            pending = events[sent:]
            for event in pending:
                payload = {
                    "job_id": event.job_id,
                    "event_type": event.event_type,
                    "message": event.message,
                    "created_at": event.created_at.isoformat(),
                    "data": event.data,
                }
                yield f"event: {event.event_type}\n"
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            sent = total

            current = get_job(job_id)
            if current is None:
                yield "event: job_failed\n"
                yield 'data: {"message":"job disappeared"}\n\n'
                break
            if current.status in TERMINAL_JOB_STATUSES and sent >= total:
                break

            yield "event: heartbeat\n"
            yield f'data: {{"job_id": "{job_id}", "status": "{current.status}"}}\n\n'
            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")