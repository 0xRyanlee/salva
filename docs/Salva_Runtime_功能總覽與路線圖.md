# Salva Runtime 功能總覽與路線圖

> Historical overview and roadmap index. Canonical contracts live under `docs/spec/`.

## What this document is for

- Provide a high-level map of the runtime
- Point readers to the canonical spec layer
- Track roadmap items without duplicating API contracts

## Canonical spec entry points

- [docs/spec/README.md](spec/README.md)
- [docs/spec/route-catalog.md](spec/route-catalog.md)
- [docs/spec/retrieval-contract.md](spec/retrieval-contract.md)
- [docs/spec/provider-contract.md](spec/provider-contract.md)
- [docs/spec/debug-playbook.md](spec/debug-playbook.md)

## Current roadmap themes

- Query intelligence refinement
- Retrieval provider expansion
- Typed relation persistence hardening
- MCP / CLI / SDK wrappers
- Docker / Compose packaging

## Operational surfaces

- `POST /v1/discover`
- `POST /v1/jobs`
- `POST /v1/pilot`
- `POST /v1/experience-plan`
- `GET /v1/routes`
- `GET /v1/providers`
- `GET /v1/providers/catalog`
- `GET /v1/evidence`
- `GET /v1/query-families`

## Debug guidance

If you are changing behavior, update the relevant spec first, then the implementation,
then the roadmap note here if the user-facing story changed.
