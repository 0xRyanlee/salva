# Audit Notes

## Existing Code Review

This directory already contains an earlier runtime prototype. It is not junk, but it is not yet a stable product boundary.

### Keep

- [core/controller.py](/Volumes/Astoria/Projects/salva/core/controller.py)
  Multi-round orchestration shape is strong and maps well to the intended runtime.
- [core/keyword_graph.py](/Volumes/Astoria/Projects/salva/core/keyword_graph.py)
  Useful query-intelligence base with telemetry feedback direction.
- [retrieval/sources/searxng.py](/Volumes/Astoria/Projects/salva/retrieval/sources/searxng.py)
  Good first retrieval adapter with fallback handling.
- [enrichment/omlx.py](/Volumes/Astoria/Projects/salva/enrichment/omlx.py)
  Useful proof that local OMLx-compatible enrichment can work.
- [processing/extractor.py](/Volumes/Astoria/Projects/salva/processing/extractor.py)
- [processing/dedup.py](/Volumes/Astoria/Projects/salva/processing/dedup.py)
- [processing/scorer.py](/Volumes/Astoria/Projects/salva/processing/scorer.py)

### Adapt

- [schema/intent.py](/Volumes/Astoria/Projects/salva/schema/intent.py)
- [schema/result.py](/Volumes/Astoria/Projects/salva/schema/result.py)

These are useful but should be merged into a single canonical contract layer with the newer [salva_core/schemas.py](/Volumes/Astoria/Projects/salva/salva_core/schemas.py).

### Retire or Relocate

- duplicate package structures that keep both `schema/` and `salva_core/`
- event-specific assumptions embedded in generic result objects
- any project-specific adapter logic that should instead live as output profiles or client adapters

## Main Risks

1. Schema divergence

There are two contract systems already. If this continues, every new adapter will fork semantics.

2. Domain leakage

The current `UnifiedResult` still carries many event-oriented fields. That makes it awkward as the foundation for a universal runtime.

3. Retrieval brittleness

Current retrieval is fallback-aware but not yet anti-bot-policy-aware.

4. Product boundary drift

Without a single canonical package structure, the project will turn back into a collection of scripts and partial modules.

## Refactor Rule

From this point, new work should follow one rule:

Every old module must be classified as either:

- keep and wrap
- adapt and migrate
- retire

No silent parallel systems.
