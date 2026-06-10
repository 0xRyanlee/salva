# E15 Findings — Budget-Matched A/B Benchmark (VP15)

`python -m experiments.computex_2026.e15_budget_ab`

**Budget:** 12 requests per condition
**Corpus:** frozen SERP fixture (no live DDG variance)
**Ground truth:** pre-declared (not pooled post-hoc)
**Fixes applied:** E11 (role nodes), E12 (snippet cap), E13 (schema purity), E14 (rotation)

## Results

| Task | Found | TP | P | R | F1 | Requests | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| naturehike | 9 | 9 | 1.00 | 0.60 | 0.75 | 9 | PASS |
| computex | 11 | 11 | 1.00 | 0.55 | 0.71 | 9 | PASS |

## Overall Verdict: **PASS**

All tasks meet P≥0.60 and R≥0.50 under equal budget and frozen corpus.
E11–E14 fixes together close the E10 recall gap.

## Development implication

The pipeline is ready for live controlled benchmarking. Next step: capture real DDG SERP for Computex 2026 exhibitors and repeat with true live provider.
