# Usage Telemetry Spec

This spec defines the tenant-aware usage read model for Salva.

## Purpose

Usage telemetry exists so callers can inspect how much the runtime is being used
without needing to query raw run/job tables directly.

## Source of truth

- API: `GET /v1/usage`
- Implementation: `salva_core/persistence/usage.py`
- Request propagation: `salva_core/schemas.py`, `salva_core/service.py`, `salva_core/worker.py`
- Manifest exposure: `bay/manifest.py`

## Tenant identity

- `DiscoveryRequest.tenant_id` is optional.
- When quota enforcement is enabled, the runtime binds requests to
  `SALVA_TENANT_ID`.
- If a caller supplies a mismatched tenant id while quota enforcement is
  enabled, the API rejects the request with `403`.
- When present and valid, the tenant id must be copied into run/job metadata.
- Aggregation must first prefer the request payload, then fall back to metadata.
- Records without a tenant id may be grouped under `unassigned`.
- When tenant quota enforcement is enabled, `GET /v1/usage` defaults to
  `SALVA_TENANT_ID` and does not expose cross-tenant aggregation.

## Aggregation contract

The usage view must aggregate at least:

- run count
- job count
- job status counts
- raw result count
- qualified result count
- source attempt count
- latest run timestamp
- latest job timestamp

The response is a read model only.
It must not mutate job, run, or usage state.

## Debug checks

- If tenant-aware reporting is missing, verify the request flow first, then the persistence aggregator.
- If counts do not match run/job tables, check whether the tenant id is present in request JSON or metadata.
- If a tenant is unassigned unexpectedly, check the caller payload before changing the aggregator.
