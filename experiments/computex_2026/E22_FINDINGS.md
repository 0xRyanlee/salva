# E22 — Memory Longitudinal Findings

**Date:** 2026-06-10
**Status:** ✅ PASS (P1 + P2 + P3)

## Hypothesis

Running the same discovery intent N times with memory persistence enabled
shows increasing memory_seeds_used across runs — the compounding mechanism
is real, not hollow.

## Method

- Frozen corpus (same 13 items as E15 — no live DDG variance)
- N=5 iterations on bd_leads/Naturehike intent
- Temporary SQLite DB stores query family memory between runs
- `read_top_query_families_for_seeding()` seeds graph before each subsequent run
- Measurements: seeds_injected, graph node count, recall, precision

## Results

| Run | seeds_injected | graph_nodes | qualified | P     | R     | F1    |
|-----|---------------|-------------|-----------|-------|-------|-------|
| 1   | 0             | 16          | 9         | 1.000 | 0.600 | 0.750 |
| 2   | 27            | 43          | 9         | 1.000 | 0.600 | 0.750 |
| 3   | 47            | 63          | 9         | 1.000 | 0.600 | 0.750 |
| 4   | 62            | 78          | 9         | 1.000 | 0.600 | 0.750 |
| 5   | 62            | 78          | 9         | 1.000 | 0.600 | 0.750 |

## Verdicts

- **P1 (seeds grow across runs):** ✅ PASS — 0 → 27 → 47 → 62
- **P2 (recall ≥ 0.50 in runs 2–5):** ✅ PASS — 0.60 throughout
- **P3 (node count grows):** ✅ PASS — 16 → 43 → 63 → 78

**Overall: ✅ PASS**

## Honest Observations

1. **Compounding is real.** Memory seeding injects new discovery angles
   (content_nodes from prior run snippets: "camping", "asmas", "handelsgesellschaft", etc.).
   Graph expands from 16 to 78 nodes by run 4.

2. **Recall does not improve** (stays at 0.60). The recall ceiling is the
   frozen corpus retriever's `results[:n]` cutoff — the last 4 ground truth
   entities never appear in the corpus sample regardless of query breadth.
   This is a benchmark limitation, not a production issue. In production, a
   richer query vocabulary from seeds could surface those entries.

3. **Plateau at run 4.** Seeds stop growing after run 4 because the frozen
   corpus's unique terms have been exhausted. In production with live
   retrieval, new snippets would continue generating novel content_nodes.

4. **Memory write mode.** This experiment uses `quarantine` (not `promote`).
   Promoting memory to global scope requires a campaing_id; the mechanism
   is available but not tested here.

## What This Proves

The compounding substrate is functional: past runs materially widen the
keyword graph before subsequent runs. The mechanism is not hollow.

## What This Does NOT Prove

- Whether wider vocabulary translates to better live recall (requires E21)
- Whether 5 runs is sufficient for convergence in production (depends on corpus richness)
- Whether `memory_write_mode=promote` compounds faster than `quarantine`
