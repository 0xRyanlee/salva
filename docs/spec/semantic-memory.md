# Semantic Memory Spec

This spec defines the query-family semantic memory surface.

## Purpose

Semantic memory exists to make future runs better than the first run.
It stores successful query-family records and exposes them through a stable search contract.

## Source of truth

- API: `GET /v1/semantic/query-families`
- API: `GET /v1/semantic/indexes`
- Implementation: `salva_core/semantic.py`
- Persistence: `salva_core/persistence/memory.py`

## Search contract

- Query-family search uses the current semantic vector plane.
- Search output must remain stable even if the vector backend changes later.
- The current built-in backend is a deterministic hybrid-hash embedding.
- The scalar-hash backend remains available as a compatibility baseline.
- Query-family search may score against the current backend and the scalar
  compatibility plane, then keep the stronger match for historical rows.
- The backend resolver may advertise future backends, but unsupported backends
  must fall back to the built-in deterministic execution path until a real
  implementation is wired in.
- The index catalog must distinguish available backends from unavailable
  optional backends in the current environment.

## Index catalog

The catalog must report:

- current backend name
- current dimensions
- available/planned backends
- backend availability status when optional modules are missing
- notes describing the current limitation and upgrade path

## Benchmark

The benchmark surface compares the current backend against the compatibility
baseline using sampled query-family records.

### API

- `POST /v1/semantic/benchmark`

### Output

- current backend name and dimensions
- sampled record count
- backend series for the current backend and compatibility baseline
- top1 objective hit rate
- top1 strategy hit rate
- mean reciprocal rank
- mean top1 similarity
- winner backend name

## Debug checks

- If semantic search quality is weak, first verify the backend catalog and dimensions.
- If the current backend is still scalar-hash, the runtime is in compatibility mode.
- If optional backends show as unavailable, the environment is missing their
  Python modules and the runtime should continue on the built-in backend.
- If memory seeding looks noisy, inspect the query-family records before changing the caller.
- If a backend swap changes response shape, the spec has been violated.
