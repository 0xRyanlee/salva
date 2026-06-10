# E17 — Diff Longitudinal Findings

**Date:** 2026-06-10
**Status:** ✅ PASS (P1 + P2 + P3 + P4)

## Hypothesis

`_compute_run_diff()` correctly surfaces entity-level changes between two runs.

## Method

- Frozen corpus (E15 Naturehike, 9 qualified entities)
- Four targeted scenarios with controlled entity mutations

## Results

| Criterion | Description | Result |
|-----------|-------------|--------|
| P1 | Identical runs → empty diff | ✅ PASS |
| P2 | Run B +1 entity → added surfaced | ✅ PASS |
| P3 | Run A entity absent in B → removed surfaced | ✅ PASS |
| P4 | Same entity with score delta >0.01 → updated surfaced | ✅ PASS |

Base run: 9 qualified entities from frozen corpus.

## What This Proves

The diff mechanism correctly identifies added, removed, and score-updated entities.
The `title|domain` keying is stable across identical runs on the same corpus.

## What This Does NOT Prove

- Whether diff is stable against non-deterministic live retrieval (entity titles may vary)
- Performance at scale (>1000 entity runs not tested)
