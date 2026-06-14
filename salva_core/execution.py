"""Execution-context helpers shared by synchronous and worker entry points."""
from __future__ import annotations

import uuid
from typing import Any

from salva_core.schemas import DiscoveryRequest


def resolve_execution_request(request: DiscoveryRequest) -> DiscoveryRequest:
    """Return a request with a stable identifier for this research continuation."""
    if request.execution.campaign_id and request.execution.continuation_id:
        return request
    token = uuid.uuid4().hex
    execution = request.execution.model_copy(
        update={
            "campaign_id": request.execution.campaign_id or f"campaign:auto:{token}",
            "continuation_id": (
                request.execution.continuation_id or f"research:{token}"
            ),
        }
    )
    return request.model_copy(update={"execution": execution})


def execution_meta(request: DiscoveryRequest) -> dict[str, Any]:
    return request.execution.model_dump(mode="json")
