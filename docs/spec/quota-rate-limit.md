# Quota and Rate-Limit Spec

This spec defines tenant quota evaluation for Salva.

## Purpose

Quota exists so tenant-scoped callers can be rate-limited before they consume
runtime work.

The current implementation is intentionally lightweight:

- no new storage tables
- no billing backend
- no tenant isolation migration

## Source of truth

- API: `GET /v1/quota`
- Enforcement: `POST /v1/discover`, `POST /v1/jobs`
- Implementation: `salva_core/quotas.py`
- Request propagation: `salva_core/schemas.py`
- Tenant binding: `SALVA_TENANT_ID`

## Policy inputs

Quota limits are read from environment variables:

- `SALVA_TENANT_HOURLY_RUN_LIMIT`
- `SALVA_TENANT_DAILY_RUN_LIMIT`
- `SALVA_TENANT_HOURLY_JOB_LIMIT`
- `SALVA_TENANT_DAILY_JOB_LIMIT`

Unset or non-positive values disable the corresponding limit.

## Enforcement contract

- If quota enforcement is enabled, `SALVA_TENANT_ID` must be configured.
- If quota enforcement is enabled and a request supplies a mismatched `tenant_id`,
  the API rejects the request with `403`.
- If quota enforcement is enabled and `tenant_id` is missing, the runtime binds
  the request to `SALVA_TENANT_ID`.
- If limits are disabled, the runtime does not reject the request.
- If a request exceeds an enabled limit, the API returns `429`.
- Quota checks must remain read-only and must not mutate storage.

## Read model

The quota response must include:

- policy state
- hourly usage
- daily usage
- remaining budget when a limit is enabled
- violated limit keys when blocked

## Debug checks

- If a tenant request is unexpectedly rejected, inspect current run/job counts
  in the hourly and daily windows.
- If quota appears disabled, verify the environment variables are set in the
  runtime process, not just the shell.
- If the API is enforcing on non-tenant traffic, check the request payload before
  changing the policy layer.
