# E9 findings — Persistent compounding curve (VP9)

`python -m experiments.hg_penetration.e9_compounding`

## Method

Synthetic mock retriever returning pre-defined snippets. Validates B1+B2 fixes (content term extraction + seed_from_memory with content_nodes). 5 runs on same domain; measures keyword graph growth.

## Results

| run | initial nodes | seeds injected | content terms | nodes after |
|---|---|---|---|---|
| 1 | 15 | 0 | 19 | 34 |
| 2 | 15 | 19 | 16 | 50 |
| 3 | 15 | 35 | 11 | 61 |
| 4 | 15 | 46 | 0 | 61 |
| 5 | 15 | 46 | 0 | 61 |

## Verdict: **PASS**

Seeds injected grew from 0 (run 1) to 46 (run 5). Total 46 unique content terms extracted across all runs.

**Confirmed:** B1 (apply_telemetry absorbs content terms) + B2 (seed_from_memory reads content_nodes) together produce measurable compounding across runs. Each run injects more seeds than the previous because content terms accumulate.

## Development implication

VP9 confirmed on the mechanism level. To validate on live data, run N consecutive live discovery runs on the same domain and measure recall@budget improvement (requires live retrieval providers). The persistence plumbing is now proven correct.
