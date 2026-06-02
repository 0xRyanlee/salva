# Salva Runtime Skill Guide

`Salva Runtime` is a discovery runtime for agents, CLI tools, and services.
Use it when you need structured retrieval, route selection, evidence, and persistence.

## Use It For

- company / lead / event / market discovery
- multi-round retrieval with fallback
- query-family memory and route reuse
- persisted jobs, telemetry, evidence chains, and relations

## Do Not Use It For

- single static web-page scraping
- hardcoded domain assumptions
- bypassing the route catalog or provider contract

## Canonical Docs

- [docs/README.md](docs/README.md)
- [docs/spec/README.md](docs/spec/README.md)
- [docs/spec/route-catalog.md](docs/spec/route-catalog.md)
- [docs/spec/retrieval-contract.md](docs/spec/retrieval-contract.md)
- [docs/spec/provider-contract.md](docs/spec/provider-contract.md)
- [docs/spec/debug-playbook.md](docs/spec/debug-playbook.md)

## Runtime Entry Points

- `POST /v1/discover`
- `POST /v1/jobs`
- `POST /v1/pilot`
- `POST /v1/experience-plan`
- `GET /v1/routes`
- `GET /v1/providers`
- `GET /v1/providers/catalog`

## Mental Model

1. Declare objective and intent.
2. Resolve route and experience profile.
3. Execute retrieval with provider fallback.
4. Normalize, score, and persist output.
5. Reuse query-family memory on later runs.

## Retrieval Sub-Tool

`salva-search` is the retrieval layer only.
It provides provider-level search, not the full pipeline intelligence layer.

See:
- [docs/spec/retrieval-contract.md](docs/spec/retrieval-contract.md)
- [docs/spec/provider-contract.md](docs/spec/provider-contract.md)
- [docs/spec/route-catalog.md](docs/spec/route-catalog.md)

## Debug Start Point

Use [docs/spec/debug-playbook.md](docs/spec/debug-playbook.md) when a route,
provider, or persistence behavior looks wrong.
