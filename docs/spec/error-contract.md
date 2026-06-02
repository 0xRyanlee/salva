# Error Contract

This spec defines how Salva surfaces failures across HTTP API, MCP, and persisted job/run records.

## Principles

- Errors should be explicit and typed by surface.
- Recoverable caller mistakes should not become generic `500`s.
- Operational failures should be persisted for later inspection.
- MCP tools should return structured JSON instead of throwing opaque traces.
- Probe and route-planning failures should identify the failing stage and topology.

## HTTP API Mapping

| Status | Meaning |
|--------|---------|
| `400` | Invalid input, malformed request, or invalid graph/view parameters |
| `403` | Tenant scope mismatch when quota enforcement is enabled |
| `404` | Missing job, run, route, preset, snapshot, or requested graph object |
| `429` | Tenant quota or rate-limit exceeded |
| `500` | Tenant quota is enabled but `SALVA_TENANT_ID` is missing |
| `500` | Unexpected internal failure or failed job execution |

The API layer uses `HTTPException` to translate domain failures into these responses.

## Persisted Error Data

- Job records persist an `error` field.
- Run records persist an `error` field where applicable.
- Telemetry and source-attempt records preserve per-provider failure detail.

This allows postmortem debugging without relying on transient process logs.

## MCP Error Envelope

MCP tools return JSON strings in the form:

```json
{ "ok": false, "error": "message" }
```

For successful calls:

```json
{ "ok": true, "...": "..." }
```

This keeps caller handling simple and avoids transport-specific exception coupling.

## Planned Rich Error Envelope

When the probe / route-planning layer is active, errors should eventually carry:

- `stage`
- `code`
- `route`
- `provider`
- `topology`
- `query`
- `message`
- `actionable_hint`

This richer shape is what the debug playbook should use to trace root cause without inspecting raw logs first.

## Operational Debugging

1. Check the API/MCP surface error code or JSON envelope.
2. If the failure is job-related, inspect the persisted job `error`.
3. If the failure is run-related, inspect run metadata and telemetry.
4. If the failure is quota-related, check tenant quota state.
5. If the failure is route/provider-related, consult the route, provider, and topology probe specs first.

Related specs:

- [route-catalog.md](route-catalog.md)
- [provider-contract.md](provider-contract.md)
- [topology-probe.md](topology-probe.md)
- [planner.md](planner.md)
- [preprompt.md](preprompt.md)
- [quota-rate-limit.md](quota-rate-limit.md)
- [debug-playbook.md](debug-playbook.md)
