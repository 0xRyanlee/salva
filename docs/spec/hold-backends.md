# Hold Backend Spec

This spec defines the Hold backend evaluation catalog.

## Purpose

Hold is currently SQLite-backed, but the runtime should expose the storage
options that were evaluated for future graph-oriented migration.

This spec is informational and does not imply a backend switch.

## Source of truth

- API: `GET /v1/hold/backends`
- Implementation: `hold/backends.py`
- Manifest exposure: `bay/manifest.py`

## Current and candidate backends

- `sqlite` is the current implementation.
- `duckdb_graph` is a candidate for analytical graph-style workloads.
- `neo4j` is a candidate for native graph traversal workloads.
- `kuzu` is a candidate for embedded graph-native workloads.

## Contract

Each backend descriptor must expose:

- `name`
- `kind`
- `status`
- `description`
- `strengths`
- `tradeoffs`
- `notes`

## Debug checks

- If a future backend is introduced, add it here before wiring callers to it.
- If the current backend changes, the runtime should preserve the snapshot and
  walk contracts or the change is too large to be a drop-in swap.
