# Confidence rebuild: retrieval-derived ranking vs flat hand-tuned gate

Board card: `salva-confidence-rebuild-ranking-signal`. Answers Q2 of
`pipelines/RETRIEVAL_CONFIDENCE_STRUCTURAL_PROBLEM.md`.

This is a pre-registered experiment. The design section below (variable,
hypothesis, metrics, adoption bar) was fixed in the experiment code
(`confidence_rebuild_experiment.py`) before any numbers were read; the metric
functions and improved/regressed counters are baked into that script, not
chosen after seeing output. Results were filled in afterward.

---

## Pre-registration (fixed before running)

### Single manipulated variable
The function that **orders the frozen accumulated candidate pool**, nothing
else:
- **Baseline** = `processing/scorer.py` flat composite (`result.relevance_score`,
  the `0.25*content_match + 0.20*contact + 0.20*signal + 0.15*region +
  0.10*source_trust + 0.10*recency` hand-tuned per-domain formula).
- **Treatment** = `processing/confidence.py::rank_candidates`
  (`0.55*content_match + 0.30*corroboration + 0.15*source_trust`), where
  `corroboration` is a retrieval-process signal: how many distinct
  `(provider, strategy, query)` formulations independently surfaced the
  candidate's registered domain across the run, log-saturated.

### Held constant
Retrieval (frozen fixtures recorded once at `qualify_threshold=0.0` so the
accumulated pool is byte-identical for both arms), extraction, dedup, and the
embedding backend. Both arms rank the exact same `UnifiedResult` objects taken
straight off the controller's `_all_results` / `_provenance`.

### Hypothesis
Retrieval-derived confidence ranks ground-truth entities higher in the pool
than the flat formula — specifically it surfaces the entity's **primary
source** and lifts precision at a tight cutoff — without lowering recall of
what retrieval already fetched.

### Metrics (per task, aggregated over the sample)
Evaluated at `K = n_gt` (tight) and `K = 10` (loose):
- `recall@K` — fraction of GT entities matched by some top-K candidate.
- `primary_hit@K` — fraction of GT entities whose GT `source_url` domain
  appears in top-K (did we rank the actual primary source high).
- `precision@K` — fraction of top-K candidates matching some GT entity.
- `recall@all` — is the GT even in the pool (retrieval ceiling; **not** moved
  by ranking, reported to separate Q1 from Q2).

Matching (evaluation only, never fed to the scorer): a candidate matches a GT
entity if its registered domain equals the GT `source_url` domain, or the GT
entity's distinctive name tokens / Chinese name appear in the candidate
title+snippet. This is a heuristic and slightly generous on name mentions.

### Adoption bar (pre-registered)
Adopt the treatment ranking iff, on the recorded sample:
1. aggregate `recall@gt` improves, **and**
2. ≥3 tasks improve on `recall@gt` with ≤1 task regressing, **and**
3. aggregate `primary_hit@gt` does not regress.

---

## Sample scope (honest declaration)

- **17 of 18** `task_set_v2` tasks. `multihop-06-advantech-cloud` is excluded:
  on replay the pipeline generates a `pirate`-strategy query that was never
  recorded (a known harness determinism edge — recency is wall-clock, so
  round convergence can differ by one strategy between record and replay;
  `harness/README.md` "Known limitation"). Not topped up rather than
  hand-fudge the frozen pool.
- **Single provider.** Only `ddgs` is reachable in this sandbox (SearXNG
  unreachable — every fixture's results carry `retrieval_instance: ddgs`).
  So `provider_diversity` is degenerate (always 1) and `corroboration`
  reduces to cross-*query* support. **The provider-diversity axis is
  implemented but UNTESTED here** — it only becomes real signal under a
  live multi-provider deployment.
- **Embeddings degraded.** No working omlx in this sandbox (localhost:8140
  returns a malformed response), so `content_match`'s semantic half silently
  falls back to `hybrid_hash` (`JinaOmlxVectorBackend._fallback`) for **both
  arms**. The comparison stays fair (identical degradation both sides) but
  absolute recall — especially cross-language 台積電↔Taiwan Semiconductor —
  is capped below what real Jina multilingual embeddings would reach.
- `n_gt = 1` for all single/crosslang tasks, so `recall@gt` there is binary
  per task (harsh at K=1); the multihop tasks carry `n_gt` 3–6.

---

## Results (17 tasks)

| metric | baseline | treatment | Δ |
|---|---|---|---|
| mean `recall@gt` | 0.686 | **0.788** | +0.102 |
| mean `primary_hit@gt` | 0.059 | **0.394** | +0.335 |
| mean `precision@gt` | 0.637 | **0.747** | +0.110 |
| mean `recall@10` | 0.906 | 0.906 | 0.000 |
| mean `recall@all` (ceiling) | 0.906 | 0.906 | — |

Task-level movement on `recall@gt`: **4 improved, 1 regressed** (12 unchanged).
On `primary_hit@gt`: **7 improved, 0 regressed**.

Improved (recall@gt): `crosslang-05-chunghwa-telecom` (0→1),
`crosslang-06-delta` (0→1), `multihop-02-tsmc-customers` (0→0.4),
`multihop-03-naturehike-dach` (0.667→1.0).
Regressed (recall@gt): `single-03-cncf` (1.0→0.0 **at K=1**; both arms still
1.0 at K=10 — treatment ranked a more-corroborated but wrong domain above
`cncf.io` at the very top slot). This is the corroboration-rewards-prolific-
domains risk, real but confined to tight-K.

Retrieval-ceiling-limited tasks (Q1, not fixable by ranking):
`multihop-04-mediatek-brands` (`recall@all=0.0` — GT never fetched) and
`multihop-02-tsmc-customers` (`recall@all=0.4`). No ranking function can
recover entities retrieval never fetched; these belong to the query-
formulation track (Q1), not this card.

---

## Verdict: ADOPT (as ordering signal), gate stays default until live-validated

The pre-registered bar is met: aggregate `recall@gt` +0.102, 4 improved / 1
regressed, and `primary_hit@gt` improves (+0.335, 0 regressions). The largest
and cleanest effect is exactly the one the structural problem named — surfacing
**primary sources** (0.059→0.394) — which the flat formula, tuned for keyword
signal not source provenance, essentially never did.

Scoped adoption, not a blank claim:
- **Adopted now:** confidence is computed for every candidate on every run
  (`controller` always calls `rank_candidates`, writes `result.confidence`),
  and `admission_policy="rank"` + the productionized scoped rerank are wired
  and available.
- **Gate remains the default `admission_policy`** until a live run with real
  Jina embeddings + ≥2 providers confirms the gain holds — because (a) the
  win rests on a signal (corroboration) that was single-provider-degenerate
  here, (b) semantic matching ran on the hash fallback, and (c) there is one
  tight-K regression whose cause (corroboration over-rewarding prolific
  domains) should be watched before it gates production output.
- **Not** a per-task symptom patch: the improvement comes from one structural
  signal (retrieval convergence) applied uniformly, not from per-domain
  keyword edits.

`recall@10` is unchanged (0.906 both) — at loose K the small pools already
contain the GT, so the ranking's value is concentrated at tight K (getting the
right entity into the top slots) and in primary-source surfacing, **not** in
recovering more of the pool. Recovering more of the pool is a retrieval
(Q1) problem, which `recall@all` bounds and which this card does not touch.

---

## What shipped

- `processing/confidence.py` — pool-level `rank_candidates` +
  `RetrievalProvenance` + `corroboration_saturation` (exhaustion signal:
  fraction of pool carrying multi-formulation corroboration).
- `core/controller.py` — accumulates provenance from raw hits; always ranks
  the pool by confidence at end of run; `admission_policy="gate"|"rank"`
  (gate default, non-breaking) + `max_admitted`. The per-round qualify flag
  still drives round-2+ keyword feedback in both modes (round dynamics
  unchanged, fixtures still replay).
- `enrichment/rerank.py` — `scoped_rerank`, the production form of the
  accumulate-then-rerank pipeline (was only a markdown-described Haiku spawn
  in `pipelines/accumulate_llm_rerank.md`). Injected LLM client, v2 primary-
  source-verification prompt, confidence-ordered passthrough when no LLM is
  reachable.
- `experiments/salva_v2/confidence_rebuild_experiment.py` — this experiment.
- Harness: `qualify_threshold` override threaded through
  `harness/task_request.py` + `harness/record_fixtures.py` (+`--all`), so the
  gate-removed full pool can be recorded and replayed deterministically.
- Tests: `tests/unit/test_confidence_ranking.py`,
  `tests/unit/test_scoped_rerank.py`.

## Necessary controller extension (declared, not scope creep)
Removing the gate from output selection needed the controller to (a) build
retrieval provenance and (b) rank the full pool at run end. Done. The gate's
round-feedback/convergence role was **kept** deliberately — collapsing it too
would change round-2+ query generation and break every recorded fixture. That
is the boundary; round-budget tuning under a fully gate-free pipeline is left
for the live-validation follow-up.

## Follow-up: rerank stage + Salva-current column

`RERANK_FULLSCALE_VALIDATION.md` (`salva-p7-rerank-fullscale-validate`)
extends this experiment with the piece left untested here: wiring
`enrichment/rerank.py::scoped_rerank` onto the confidence-ranked pool, plus a
real "Salva-current" gate-pipeline column (not a pool-slice proxy). It also
notes `multihop-06-advantech-cloud`'s fixture gap, open when this experiment
ran, has since been topped up — that file's sample is 18/18, not 17/18. This
file's own 17-task numbers above are unchanged and not retroactively edited.
