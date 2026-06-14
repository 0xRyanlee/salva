# Agent-only vs Salva Experiments

This directory contains independently collected observations, raw Salva output,
evaluation code inputs, reports, and charts.

## Naturehike DACH Live Dogfood

![Naturehike DACH comparison](results/naturehike-dach-comparison.svg)

| Condition | Round | Verified relevant | Pooled recall | Country coverage | Channel coverage |
|---|---:|---:|---:|---:|---:|
| Agent-only | 1 | 5 | 29.4% | 100.0% | 40.0% |
| Agent-only | 2 | 11 | 64.7% | 100.0% | 80.0% |
| Agent-only | 3 | 15 | 88.2% | 100.0% | 100.0% |
| Salva | 1 | 2 | 11.8% | 33.3% | 20.0% |
| Salva | 2 | 0 | 0.0% | 0.0% | 0.0% |
| Salva | 3 | 0 | 0.0% | 0.0% | 0.0% |

This is a live ecological dogfood result, not a controlled benchmark. Pooled
recall uses the post-hoc verified union of both paths, not predeclared external
ground truth. The conditions did not have matched request/time budgets;
Agent-only raw SERPs were not fully captured; elapsed time is not comparable.
Salva R1/R2/R3 are independent max-round snapshots, and R3 stopped after two
empty rounds.

The result is still useful for failure analysis:

- Salva found two relevant specialist retailers in R1 but no distributors,
  agents, or retail alliances.
- It returned a duplicate Bergfreunde entity across `.eu` and `.de`.
- DDG HTML provider variability produced zero-result R2/R3 runs.
- Multi-round expansion cannot improve results when the provider supplies no
  evidence.

## Reproduce

Collect Salva snapshots without persistence or cross-run memory:

```bash
OBSCURA_BIN=/nonexistent SEARXNG_ENABLED=false \
  .venv/bin/python scripts/collect_salva_observation.py \
  --rounds 1 \
  --output experiments/agent_vs_salva/raw/salva-r1.json
```

Evaluate annotated observations and generate GitHub-ready artifacts:

```bash
.venv/bin/python scripts/compare_agent_mode.py \
  experiments/agent_vs_salva/naturehike-dach-live.json \
  --json-out experiments/agent_vs_salva/results/naturehike-dach-report.json \
  --markdown-out experiments/agent_vs_salva/results/naturehike-dach-report.md \
  --svg-out experiments/agent_vs_salva/results/naturehike-dach-comparison.svg
```

Run deterministic isolation/adversarial checks:

```bash
.venv/bin/python scripts/run_isolation_experiment.py \
  --output experiments/agent_vs_salva/isolation-report.json
```

## Files

- `naturehike-dach-live.json`: annotated independent observations
- `raw/salva-r*.json`: unmodified Salva output, telemetry, and source attempts
- `results/naturehike-dach-report.json`: calculated metrics
- `results/naturehike-dach-report.md`: result table and validity warnings
- `results/naturehike-dach-comparison.svg`: quality comparison chart
- `isolation-report.json`: deterministic campaign/memory adversarial checks

## Next Experimental Methods

At least two methods should be used before claiming a general quality advantage:

1. **Frozen-corpus replay**: both conditions receive the same timestamped HTML
   corpus. Controls provider drift and allows complete raw-result capture.
2. **Budget-matched live A/B**: same request count, wall-clock ceiling, countries,
   and query languages; repeat at least five times and report confidence ranges.
3. **Round ablation**: compare Salva 1/2/3 rounds using one provider snapshot,
   then attribute marginal gain or loss per round.
4. **Memory ablation**: `none` vs `campaign_all` vs `campaign_promoted`; report
   pooled-recall gain, contamination, and query diversity.
5. **Cross-campaign poisoning**: inject a high-score fake vendor into campaign A
   and prove zero appearance in campaign B.
6. **Indirect prompt-injection corpus**: pages contain instructions to alter the
   task, exfiltrate context, or promote a source; verify no tool authority change.
7. **Provider resilience matrix**: SearXNG, DDG, Whoogle, and frozen corpus under
   timeout, 403, empty result, malformed HTML, and duplicate-domain conditions.
8. **Blind human relevance review**: remove condition labels, use two reviewers,
   record agreement and adjudication.
9. **Country/channel strata**: report Germany/Austria/Switzerland and distributor/
   agent/alliance/retailer separately so aggregate pooled recall cannot hide gaps.
10. **Repeatability**: rerun each condition with fixed manifests and report result
    overlap, metric variance, and provider error rate.
