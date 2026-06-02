# Hold Walk Spec

This spec defines the relation-aware retrieval surface over a stored run snapshot.

## Purpose

The walk surface exists so callers can traverse the materialized Hold graph without
choosing a backend graph engine first.

## Source of truth

- API: `GET /v1/hold/walk`
- Implementation: `hold/walk.py`

## Walk inputs

- `run_id`
- `seed_entity_id`
- `depth`
- `include_evidence`
- `include_sources`

## Walk output

The response must include:

- seed entity IDs
- walk depth
- graph nodes
- graph edges
- generated timestamp

Node kinds:

- `entity`
- `relation`
- `evidence`
- `source`
- `hyperedge`

## Walk behavior

- Relations are expanded first.
- Evidence records are attached to matching entities, relations, and hyperedges.
- Source nodes are attached beneath evidence when `include_sources` is true.
- The walk is read-only and derived from a run snapshot.

## Debug checks

- If the walk returns no nodes, verify the run snapshot contains the seed entity.
- If sources are missing, check evidence linkage and `include_sources`.
- If relation expansion is incomplete, inspect the persisted relation records for the run.
