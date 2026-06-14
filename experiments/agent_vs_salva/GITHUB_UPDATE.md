# Execution-Isolated Research and Agent-vs-Salva Dogfood

## What changed

- Added `ExecutionContext` across REST, CLI, MCP, SDK, and workers.
- Cross-run memory reads now default to `none`.
- Memory writes default to review-gated `quarantine`.
- Added campaign-scoped promoted memory and a promotion endpoint.
- Added `persistence=none` for zero-write runs.
- Prevented caller `source_hints` from becoming trusted-source entries.
- Replaced the old mocked advice comparison with an observation-based evaluator.
- Added JSON, Markdown, and SVG experiment artifacts.

## Dogfood result

Naturehike DACH channel discovery, 2026-06-08:

| Condition | R1 verified | R2 verified | R3 verified | Best pooled recall |
|---|---:|---:|---:|---:|
| Agent-only | 5 | 11 cumulative | 15 cumulative | 88.2% |
| Salva | 2 | 0 snapshot | 0 snapshot | 11.8% |

This is not a controlled benchmark. Pooled recall uses the post-hoc verified
union, budgets were unmatched, Agent raw SERPs were not fully captured, and
Salva live provider output varied between runs. The value is the failure
evidence: provider instability, duplicate entities, and missing channel-type
coverage are now reproducible and visible.

![Comparison](results/naturehike-dach-comparison.svg)

## Reproduce

```bash
.venv/bin/pytest -q -p no:cacheprovider \
  tests/test_execution_context.py \
  tests/test_compare_agent_mode.py

.venv/bin/python scripts/run_isolation_experiment.py \
  --output experiments/agent_vs_salva/isolation-report.json
```

See `experiments/agent_vs_salva/README.md` for collection and evaluation commands.
