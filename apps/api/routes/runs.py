"""
Runs API routes: /v1/runs, /v1/runs/{run_id}
"""
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from salva_core.persistence import get_run, list_runs
from salva_core.schemas import RunsResponse

router = APIRouter()


@router.get("/runs", response_model=RunsResponse)
async def runs(
    limit: Annotated[int, Query(ge=1, le=200)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    campaign_id: Annotated[str | None, Query()] = None,
    continuation_id: Annotated[str | None, Query()] = None,
) -> RunsResponse:
    """List all discovery runs"""
    items, total = list_runs(
        limit=limit,
        offset=offset,
        campaign_id=campaign_id,
        continuation_id=continuation_id,
    )
    return RunsResponse(items=items, total=total)


@router.get("/runs/{run_id}")
async def run_detail(run_id: str) -> dict[str, object]:
    """Get run details"""
    item = get_run(run_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return item
