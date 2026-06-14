"""
Shared dependencies for API routes
"""
import os

from fastapi import HTTPException

from salva_core.quotas import load_quota_policy
from salva_core.schemas import TenantQuotaResponse


def resolve_tenant_scope(tenant_id: str | None, action: str) -> str | None:
    """Resolve tenant scope for the current request"""
    policy = load_quota_policy()
    if not policy.enabled:
        return tenant_id

    configured_tenant = os.getenv("SALVA_TENANT_ID", "").strip()
    if not configured_tenant:
        raise HTTPException(
            status_code=500,
            detail="SALVA_TENANT_ID must be set when tenant quota enforcement is enabled",
        )

    if tenant_id and tenant_id.strip() and tenant_id.strip() != configured_tenant:
        raise HTTPException(
            status_code=403,
            detail=f"tenant_id does not match configured tenant scope for {action}",
        )

    return configured_tenant


def ensure_quota_allowed(quota: TenantQuotaResponse, action: str) -> None:
    """Ensure tenant has quota allowance for the action"""
    if quota.allowed:
        return
    message = ", ".join(quota.violated) if quota.violated else "quota exceeded"
    raise HTTPException(
        status_code=429,
        detail=f"Tenant quota blocked {action}: {message}",
    )