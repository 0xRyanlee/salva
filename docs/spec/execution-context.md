# Execution Context Contract

`ExecutionContext` is the caller-visible contract for research scope, persistence,
cross-run memory, and cache intent. The agent declares policy; Salva enforces it.

## Default Contract

```json
{
  "campaign_id": "campaign:auto:<generated>",
  "continuation_id": "research:<generated>",
  "persistence": "audit",
  "memory": {
    "read_scope": "none",
    "write_mode": "quarantine",
    "min_success_score": 0.3
  },
  "cache": {
    "mode": "ephemeral",
    "ttl_hours": 24,
    "retain_artifacts": false
  },
  "tags": {}
}
```

These defaults are fail-closed for cross-run reuse:

- A single Salva call may still execute multiple rounds in memory.
- Past query-family memory is not read automatically.
- A missing campaign ID is resolved to a unique auto campaign before execution.
- New query-family memory is written as `quarantine`, not trusted reuse material.
- The run is retained as an audit record unless `persistence=none`.
- No project-root graph/cache file is required for normal multi-round execution.

## Fields

| Field | Values | Required behavior |
|---|---|---|
| `campaign_id` | caller-defined stable ID | Isolation key for campaign memory and run filtering |
| `continuation_id` | caller-defined or generated ID | Identifies one research thread/run continuation |
| `persistence` | `audit`, `none` | `none` disables all database writes and memory writes |
| `memory.read_scope` | `none`, `campaign_promoted`, `campaign_all`, `global_legacy` | Controls which prior query families may seed the graph |
| `memory.write_mode` | `none`, `quarantine`, `promote` | Controls whether new memory is absent, review-gated, or immediately reusable |
| `memory.min_success_score` | `0..1` | Minimum stored success score for seeding |
| `cache.mode` | `ephemeral`, `content_addressed` | Declares cache intent; only `ephemeral` is currently implemented |
| `tags` | string map | Audit metadata only; tags never grant access |

Campaign read scopes require a `campaign_id`. Validation fails before retrieval
if the scope is invalid.

## Memory State Machine

```text
new telemetry
  ├─ write_mode=none       -> no query-family memory
  ├─ write_mode=quarantine -> quarantine
  └─ write_mode=promote    -> promoted

quarantine --review/promote endpoint--> promoted
```

`campaign_promoted` reads only promoted rows in the same campaign.
`campaign_all` explicitly opts into both quarantine and promoted rows in the
same campaign. `global_legacy` reads only rows marked `legacy`; it is the
compatibility escape hatch and should not be used for sensitive or multi-tenant
research.

## Responsibility Boundary

| Layer | Owns |
|---|---|
| Agent/orchestrator | objective, campaign ID, continuation ID, budgets, whether prior memory is desired |
| Salva runtime | validation, campaign filters, quarantine/promotion, audit persistence, no-write enforcement |
| Deployment platform | authentication, tenant authorization, filesystem roots, secrets, database permissions |

The agent should pass identifiers and policies, not database paths. Filesystem
placement is a deployment concern.

## API Example

```json
{
  "objective": "find_companies",
  "intent": {
    "market": "Germany Austria Switzerland",
    "industry": "outdoor equipment",
    "product": "camping equipment",
    "role": "distributor"
  },
  "execution": {
    "campaign_id": "naturehike-dach-2026",
    "continuation_id": "channel-map-r1",
    "persistence": "audit",
    "memory": {
      "read_scope": "campaign_promoted",
      "write_mode": "quarantine"
    }
  }
}
```

Review and promote one query family:

```http
POST /v1/query-families/{memory_id}/promote?campaign_id=naturehike-dach-2026
```

## Cache Status

Within-call multi-round state is in memory and disappears when the call ends.
The current runtime does not create a KeywordGraph cache in the repository root.
SQLite audit/memory rows are persistent data, not a cache.

`content_addressed` is reserved in the type vocabulary but its artifact backend,
TTL cleanup, and integrity manifest are not implemented yet. Validation rejects
that mode until the backend exists; callers must use `ephemeral`.
