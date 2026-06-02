# Job Storage Spec

This spec defines the job record contract for tenant-aware execution.

## Purpose

Job storage exists to track queued, running, completed, and failed discovery
work items while keeping a stable read model for callers and workers.

## Source of truth

- API: `POST /v1/jobs`
- API: `GET /v1/jobs`
- API: `GET /v1/jobs/{job_id}`
- API: `GET /v1/jobs/{job_id}/events`
- Implementation: `salva_core/persistence/jobs.py`
- Request propagation: `salva_core/schemas.py`, `salva_core/service.py`, `salva_core/worker.py`

## Tenant behavior

- `DiscoveryRequest.tenant_id` is optional.
- When present, `jobs.tenant_id` must be stored on creation.
- If the row was created before tenant support existed, readers may fall back to
  `meta_json.tenant_id`.
- `JobRecord` must expose `tenant_id` explicitly.

## Read model contract

Job reads must include:

- `job_id`
- `status`
- `objective`
- `output_profile`
- `tenant_id`
- `created_at`
- `updated_at`
- `request`
- `run_id`
- `error`
- `meta`

## Debug checks

- If a job has a tenant in `meta` but not in the row, migrate the row on update
  or backfill it during read.
- If job APIs return ambiguous ownership, check `jobs.tenant_id` before reading
  deeper metadata.
