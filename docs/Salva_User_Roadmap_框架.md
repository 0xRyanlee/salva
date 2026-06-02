# Salva Runtime — User Roadmap & Routing Framework

> Roadmap and UX index only. Canonical behavior specs live under `docs/spec/`.

## Use this document for

- Understanding where a user or agent should enter the system
- Comparing high-level journey types
- Tracking the remaining roadmap work

## Read first

- [spec/README.md](spec/README.md)
- [spec/route-catalog.md](spec/route-catalog.md)
- [spec/retrieval-contract.md](spec/retrieval-contract.md)
- [value-model.md](value-model.md)

## Journey classes

- **Hot path**: single lookup, low latency, one round
- **Cold path**: async job, multi-round, persistent trace
- **Deep path**: enrichment, evidence chains, hypergraph
- **Meta path**: pilot, mate, semantic memory, route reuse

## Routing dimensions

- Query hop depth
- Output schema complexity
- Caller type
- Provider fallback pressure
- Memory bootstrap usage

## Current roadmap focus

- Make route selection visible to callers
- Keep retrieval provider contracts explicit
- Reduce coupling between route planning and provider execution
- Improve debugability with stable spec files

## Notes

This file should stay short. If a section starts looking like a contract,
move it into `docs/spec/` instead.
