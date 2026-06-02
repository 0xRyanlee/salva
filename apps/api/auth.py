"""
Static API key authentication for Salva REST API.

Configure via environment variable:
    SALVA_API_KEY=your-secret-key

If SALVA_API_KEY is not set (empty string), authentication is disabled —
intended for local development only. Never deploy without a key.

Usage in FastAPI routes:
    from apps.api.auth import require_auth
    @app.get("/v1/runs")
    async def list_runs(auth: Annotated[None, Depends(require_auth)]):
        ...
"""
from __future__ import annotations

import os
from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

_API_KEY = os.getenv("SALVA_API_KEY", "")
_HEADER  = APIKeyHeader(name="X-Salva-Key", auto_error=False)


async def require_auth(api_key: Annotated[str | None, Security(_HEADER)] = None) -> None:
    if not _API_KEY:
        return  # dev mode: no key configured → open
    if api_key != _API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Salva-Key header",
            headers={"WWW-Authenticate": "ApiKey"},
        )
