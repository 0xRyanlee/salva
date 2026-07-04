# Baseline vs current Salva pipeline vs accumulate+LLM-rerank — first comparative round

**Date:** 2026-07-04
**Scope:** all 6 `find_partnership_signals` (multihop) tasks in `task_set_v1.json`
— the tier where Salva's current pipeline fails hardest (0/6 qualified
contribution, per `RESCORE_COMPARISON.md`, unchanged even after the scorer
fix). This is the tier where a real alternative would matter most if one
exists.

**Headline: both new pipeline directions massively outperform Salva's
current isolated pipeline on this tier, and land close to each other.**
Neither is a universal win over the other — each has a distinct, specific
failure mode, both traced to concrete causes below, not asserted.

## Three conditions compared

1. **Salva-current (isolated)** — Salva's own scored pipeline,
   `qualify_threshold` at the domain-calibrated default, **with no
   WebSearch fallback** — i.e., exactly what Salva itself contributes,
   not mixed with an agent's independent search (that mixed condition is
   what Phase 3's Arm B tested; this comparison isolates Salva's own
   contribution specifically, since that's the variable being redesigned).
   Numbers below are Salva's own `qualified_count` from
   `RESCORE_COMPARISON.md`'s post-scorer-fix rerun.
2. **Baseline (bare N-round agent)** — `pipelines/baseline_multiround.md`,
   no Salva involvement, 3 explicit rounds, Haiku throughout.
3. **Accumulate+LLM-rerank** — `pipelines/accumulate_llm_rerank.md`: Salva's
   real multi-round retrieval runs unmodified (`qualify_threshold=0.0`
   surfaces every raw candidate), then a single Haiku pass filters/reranks.

## Recall vs ground truth (`task_set_v1.json`)

| task | ground truth count | Salva-current (isolated) | Baseline | Accumulate+rerank |
|---|---:|---:|---:|---:|
| multihop-01-cncf-founders | 6 | 0/6 | **6/6** | 6/6 (but 1 extraneous wrong entity included, see below) |
| multihop-02-tsmc-customers | 5 | 0/5 | **5/5** | 5/5 |
| multihop-03-naturehike-dach | 3 | 0/3 | 2/3 | 2/3 |
| multihop-04-mediatek-brands | 5 | 0/5 | **5/5** | 5/5 |
| multihop-05-gleif-regulators | 4 | 0/4 | **4/4** | 3/4 (missed OFR specifically) |
| multihop-06-advantech-cloud | 3 | 0/3 | 2-2.5/3 (Alibaba flagged weak) | 3/3 (Alibaba included, also flagged weak) |
| **Total** | **26** | **0/26** | **~24.5/26** | **~24/26** |

**Salva-current's 0/26 is not a rounding artifact** — it is exactly what
`RESCORE_COMPARISON.md` already established: the scorer-layer gap holds
even after the domain-config fix. Both new directions clear this bar by a
wide margin on every single task.

## Where each variant specifically failed (not just aggregate scores)

- **multihop-01 (CNCF founders), accumulate+rerank only**: recall hit 6/6,
  but the answer *also* included RX-M, a December-2015 joiner incorrectly
  bundled into an oft-cited "13-name" abbreviated list — an actual
  false-positive precision cost, not just an incomplete answer. Root
  cause, traced precisely: the rerank step could only judge the 21 raw
  candidates Salva's own retrieval rounds fetched, which included a
  Wikipedia summary carrying that same imprecise 13-name list, but never
  fetched CNCF's own original July-2015 press release. The bare-agent
  baseline avoided this because it independently searched further and
  found CNCF's own announcement directly, catching the discrepancy itself.
  **This confirms the diagnosis from `accumulate_llm_rerank.md`'s own
  validation run: the rerank step's ceiling is capped by what the
  retrieval rounds actually fetched — it cannot go get a better primary
  source on its own.**
- **multihop-03 (Naturehike DACH), both variants**: both missed one
  ground-truth entity (`Naturehike.de (Walthaus Outdoor)` specifically as
  a *distributor* entity) — both variants independently concluded, via
  real research, that naturehike.de/naturehike-shop.com read as the
  brand's own **direct-to-consumer storefronts**, not a third-party
  distributor, which is arguably a *more accurate* characterization of
  reality than the original ground truth's framing (which listed it as a
  distributor). This is the deliberately-thin-evidence task by design
  (per `TASK_SET_README.md`) — both variants handled the genuine ambiguity
  honestly rather than forcing a match, which is the correct behavior this
  task was built to test.
- **multihop-05 (GLEIF regulators), accumulate+rerank only**: missed the
  U.S. Office of Financial Research specifically, though it independently
  found CFTC, SEC, ESMA, IOSCO, CPMI, and correctly identified the LEI ROC
  and FSB (the two most important governance entities) — a real but minor
  gap, not a systemic failure on this task.
- **multihop-06 (Advantech cloud), Salva-current only**: total failure
  (0/3) versus both new directions correctly identifying Microsoft Azure
  and AWS with strong sourcing, and Alibaba Cloud with appropriately
  flagged weaker evidence in both variants independently — a consistent,
  honest signal (not just one variant getting lucky) that Alibaba's
  relationship really is less strongly documented than Azure/AWS's.

## Cost comparison

- **Baseline**: fixed budget, 9 WebSearch queries per task (3 rounds × 3),
  every task, regardless of difficulty.
- **Accumulate+rerank**: 1 Salva call (internal retrieval, not an external
  WebSearch query) + variable supplemental WebSearch when the raw pool
  proved insufficient. Notably, `multihop-01` needed **zero** supplemental
  search — the rerank agent answered purely from Salva's own raw pool
  (accepting the RX-M imprecision cost documented above as the tradeoff).
  Other tasks needed 2-6 supplemental queries when the raw pool didn't
  cover the question.

This is a real, if modest, efficiency signal for accumulate+rerank: when
Salva's underlying retrieval already surfaces usable raw signal (even if
none of it would have cleared the old scoring gate), the rerank step can
sometimes skip external search entirely — cost the baseline can never
avoid, since it has no retrieval infrastructure of its own to lean on.

## What this round of comparison actually establishes

Directly answering the question that motivated this whole research
direction (**"is the bottleneck too few data sources, or too-strict
scoring/similarity requirements?"**): **neither, cleanly — it's the
scoring GATE mechanism specifically**, not the vocabulary calibration
(`RESCORE_COMPARISON.md`'s original hypothesis) and not data source
coverage (Salva's own retrieval, freed from the gate via
`qualify_threshold=0.0`, found relevant candidates buried in its raw pool
for every task tested — the data was often already there). The moment the
mechanistic per-round keyword-matching gate is removed — whether by
routing everything to an LLM rerank pass, or by not gating at all (the
bare-agent baseline never had a gate to begin with) — recall jumps from
0/26 to ~24/26 on the exact tier where the gate was failing hardest.

This reframes the earlier `RESCORE_COMPARISON.md` diagnosis
(signal-vocabulary/trusted-source mismatch) as **one true but narrower
symptom of a broader problem**: any fixed, hand-tuned, per-round
mechanistic scoring gate is going to keep missing real signal phrased in
ways the gate's author didn't anticipate, no matter how well-calibrated
the vocabulary gets for the cases already seen. An LLM judging relevance
directly generalizes to phrasings a fixed keyword list can't be tuned
for in advance.

## Honest limitations of this round

- 6 tasks, not 18 — chosen deliberately as the hardest tier, not a
  full-scale re-run. A wider validation across `crosslang`/`single` tiers
  (where Salva's current pipeline already does contribute something,
  per `ANALYSIS_FINDINGS.md`) is a natural next round, not done here.
- Accuracy scoring above (`6/6`, `5/5`, etc.) is manual/qualitative
  matching against `task_set_v1.json`'s ground truth entities, same
  method as the rest of this session's experiments — not an automated
  scorer.
- The `qualify_threshold=0.0` technique surfaces Salva's raw retrieval
  pool faithfully, but this comparison did not test whether Salva's
  retrieval itself (its query formulation, KeywordGraph expansion) is
  optimal — only whether gating vs. not-gating matters, holding retrieval
  constant. `multihop-01`'s precision cost is itself evidence that
  retrieval quality (not just the gate) is a real, separate lever worth
  investigating next.

## Recommended next iteration (not started here)

Per the ongoing, non-stopping nature of this research direction: the
clearest next move is not another rerank-prompt tweak, but attacking the
**retrieval query-formulation gap** the CNCF case exposed — e.g., testing
whether letting the rerank LLM *request one follow-up search* when it
judges the raw pool insufficient (rather than being purely read-only over
whatever Salva's rounds happened to fetch) closes the gap between
accumulate+rerank and the bare-agent baseline, which has no such
constraint. A second, independent direction worth carrying forward per the
user's own suggestion: adding DOM-simulated live-browser search (via the
existing `ObscuraBrowserRetriever`) as an additional free data source
feeding the same accumulate+rerank pool, to test whether broader retrieval
coverage — not just removing the gate — narrows the gap further.
