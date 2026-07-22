# Rerank full-scale validation: three-way recall comparison

Board card: `salva-p7-rerank-fullscale-validate`. Extends
`CONFIDENCE_REBUILD_FINDINGS.md` (`salva-confidence-rebuild-ranking-signal`),
which pre-registered and validated **only the ranking-order signal**
(flat scorer vs `processing/confidence.py::rank_candidates`) on 17/18 tasks
and explicitly left the LLM rerank stage untested. This file adds the piece
that experiment named but didn't run: `enrichment/rerank.py::scoped_rerank`
wired onto the confidence-ranked pool, plus a genuine third column — the
actual default gate pipeline's output (not a pool-slice proxy for it).

Script: `experiments/salva_v2/rerank_fullscale_validation.py`. Reuses
`confidence_rebuild_experiment.py`'s pool capture, matching heuristic, and
K-based eval functions by import — same evaluation method, not a rewrite.

---

## Pre-registration addendum (fixed before reading results)

### Three columns
1. **Salva-current** — `SalvaController` run with production defaults
   (`qualify_threshold=None` → domain-calibrated gate, `admission_policy=
   "gate"`, the controller's default). This is literally what
   `execute_discovery()` returns to a caller today. No K-slicing — evaluated
   over the *entire* selected/qualified set, however large that is (varies
   0–5 across tasks; see caveat below).
2. **baseline (accumulate, no rerank)** — same definition as
   `CONFIDENCE_REBUILD_FINDINGS.md`'s baseline column: `qualify_threshold=0.0`
   pool, ordered by `processing/scorer.py`'s flat composite, evaluated at
   `K=n_gt` (tight) and `K=10` (loose).
3. **accumulate+rerank** — the same `qualify_threshold=0.0` pool, ordered by
   `rank_candidates` (confidence), top-25 handed to `scoped_rerank`, kept
   items evaluated at the same `K=n_gt`/`K=10`.

### What's newly manipulated vs. the prior experiment
`CONFIDENCE_REBUILD_FINDINGS.md`'s treatment column was confidence-ordering
only. Column 3 here adds the LLM filter/rerank stage on top of that ordering.
Column 1 is new — the prior experiment never replayed the real gate pipeline;
it only compared two orderings of the *ungated* pool.

### Metrics
Identical definitions to `CONFIDENCE_REBUILD_FINDINGS.md`: `recall@K`,
`primary_hit@K`, `precision@K`, matching heuristic (domain match or
distinctive name-token/CJK-term match in title+description), evaluation-only
(never fed to ranking/rerank).

### Adoption-relevant question this file answers
Does adding the LLM rerank stage on top of confidence-ranking change recall
(up or down) relative to confidence-ranking alone, and how does the whole
accumulate+rerank variant compare to what the current gate pipeline actually
returns today?

---

## Environment finding (read before the numbers): omlx endpoint is up but broken

`http://127.0.0.1:8140/v1/models` responds normally (lists `gemma-4-e2b-it-
4bit`, `Qwen3.5-9B-MLX-4bit`, jina embedding/reranker models). But every
`/v1/chat/completions` call — tested directly via `curl` and via
`OmlxProviderAdapter.complete()`, with both models, with and without a
system message, with default and 20s timeouts — returns `HTTP 500 Internal
Server Error` with an empty error body. This is a server-side fault, not a
payload/timeout issue on the caller side.

Consequence: `scoped_rerank()` calls `complete_with_omlx`, which catches the
exception and returns `available=False`. Every one of the 18 tasks in this
run degrades to the documented confidence-ordered passthrough
(`RerankResult.llm_available=False`, `notes=["llm_unavailable_passthrough"]`,
`dropped_count=0`). This matches — does not newly discover — the omlx
degradation `CONFIDENCE_REBUILD_FINDINGS.md` already flagged ("No working
omlx in this sandbox"); it is now pinned to a specific cause (`/v1/models`
works, `/v1/chat/completions` 500s) rather than "malformed response."

**This caps what this validation can claim.** Passthrough is order-preserving
and non-lossy by construction — under passthrough, `accumulate+rerank`'s
recall numbers are mathematically the confidence-ranking numbers
(`CONFIDENCE_REBUILD_FINDINGS.md`'s treatment column), extended here to the
18th task. This run validates that **the production `scoped_rerank` wiring
integrates cleanly with the confidence-ranked pool and degrades safely** (no
crash, no silent corruption, no reordering, across all 18 tasks) — it does
**not** validate that a real LLM call actually improves precision/discards
noise at scale. That question is still open beyond the single hand-run
`multihop-01` case in `pipelines/accumulate_llm_rerank.md` (which used a
Haiku agent, not omlx, and was 1 task, not 18).

## Implementation note (methodology correctness, not a finding)

`scoped_rerank`'s `{name, url, claim}` output schema is intentionally terse —
it's what the LLM itself is asked to produce, not a lossy record of the full
candidate. Scoring the terse stub directly against ground truth would
conflate "the LLM/passthrough dropped this" with "the eval heuristic lost
its snippet-based match signal" — caught concretely on `crosslang-06-delta`,
whose only match evidence (CJK term `台達電子`) lives in the original
`description`, not the `title` echoed into `name`. Fixed by mapping each kept
`url` back to the original full-fidelity candidate from the confidence-
ranked pool before evaluating — the same reconciliation any real caller would
do to keep a rerank verdict's other fields (location, organizer, etc.)
intact. Noted here because it's exactly the kind of wiring detail
`salva-p7-production-wire-rerank-mode` will need to get right.

---

## Sample scope

**18/18 tasks**, not 17. `multihop-06-advantech-cloud`'s `pirate`-strategy
fixture — missing when `CONFIDENCE_REBUILD_FINDINGS.md` ran, per its
documented exclusion — is now present in `experiments/salva_v2/fixtures/`
(topped up since, exact provenance not tracked in git — fixtures are
untracked). Pool capture (`qualify_threshold=0.0`) succeeded cleanly for all
18 tasks with no `FixtureMissingError`, so it's included here without
fabricating anything. `CONFIDENCE_REBUILD_FINDINGS.md`'s own 17-task numbers
are unchanged by this — this file doesn't retroactively edit that experiment.

**Salva-current (gate) column: 17/18.** Fixtures were recorded at
`qualify_threshold=0.0` (every round-1 candidate "qualifies"). Replaying with
the domain-calibrated gate default (`~0.35`–`0.40`) changes which round-1
candidates are marked `qualified`, which can make round-2+ query generation
diverge from what was recorded — the harness's documented "Known
limitation" (`harness/README.md`). It did, once: `single-03-cncf`'s round-2
`radar` strategy requested `"CNCF founded Global"`, never recorded (only
`"CNCF" site:crun...` was recorded for that strategy under the 0.0-threshold
run). Reported as `N/A` in the gate column for that task, not faked or
backfilled. All other 17 gate replays completed without error.

---

## Results — three-way recall table (18 tasks, all numbers real per-task, none averaged-only)

`gate` = Salva-current, full selected-set recall (no K — see caveat below the
table). `base@K` / `rrk@K` = baseline / accumulate+rerank at K=n_gt (tight)
and K=10 (loose).

| task_id | tier | n_gt | gate | base@gt | rrk@gt | base@10 | rrk@10 |
|---|---|---|---|---|---|---|---|
| single-01-tsmc | single | 1 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| single-02-naturehike | single | 1 | 0.0 | 0.0 | 0.0 | 1.0 | 1.0 |
| single-03-cncf | single | 1 | **N/A** (fixture gap) | 1.0 | **0.0** | 1.0 | 1.0 |
| single-04-mediatek | single | 1 | 0.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| single-05-advantech | single | 1 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| single-06-gleif | single | 1 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| crosslang-01-tsmc | crosslang | 1 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| crosslang-02-asus | crosslang | 1 | 0.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| crosslang-03-acer | crosslang | 1 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| crosslang-04-foxconn | crosslang | 1 | 0.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| crosslang-05-chunghwa-telecom | crosslang | 1 | 0.0 | 0.0 | **1.0** | 1.0 | 1.0 |
| crosslang-06-delta | crosslang | 1 | 0.0 | 0.0 | **1.0** | 1.0 | 1.0 |
| multihop-01-cncf-founders | multihop | 6 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| multihop-02-tsmc-customers | multihop | 5 | 0.0 | 0.0 | **0.4** | 0.4 | 0.4 |
| multihop-03-naturehike-dach | multihop | 3 | 0.0 | 0.667 | **1.0** | 1.0 | 1.0 |
| multihop-04-mediatek-brands | multihop | 5 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| multihop-05-gleif-regulators | multihop | 4 | 0.5 | 1.0 | 1.0 | 1.0 | 1.0 |
| multihop-06-advantech-cloud | multihop | 3 | 0.0 | 0.0 | 0.0 | 0.667 | 0.667 |
| **mean** | | | **0.382** (n=17) | **0.648** | **0.744** | **0.893** | **0.893** |

Bold = improved vs. baseline at that K. `single-03-cncf` bold = regressed.

### Gate column caveat (read before comparing gate to the other two)

The `gate` column is recall over the **entire** selected set the current
pipeline actually returns — not sliced to a fixed K. Selected-set size varies
0–5 across tasks (`single-06-gleif`: 4 items; `multihop-05`: 1 item against
`n_gt=4`; `single-04-mediatek`/`crosslang-02/04`/`multihop-03/04/06`: 0
items). So the `gate` numbers aren't at "the same K" as `base@10`/`rrk@10` —
part of the gap is the gate's set frequently being *smaller* than the loose
K=10 window the other columns get evaluated at, not purely misranking within
an equal-size window. That's not a methodology flaw to correct — it's
exactly what "what does Salva-current actually hand back to a caller today"
means, unslicing included.

### Regressions (honest, not smoothed over)

**`single-03-cncf`, `rrk@gt`: 1.0 → 0.0.** Identical to the single regression
`CONFIDENCE_REBUILD_FINDINGS.md` already found and named — corroboration
(cross-query support) ranks a more-corroborated wrong domain above
`cncf.io` at the tight K=1 slot. Both arms are still 1.0 at K=10. This is a
carry-over of the already-known risk, not a new failure introduced by the
rerank stage (rerank ran in passthrough here, so it couldn't have introduced
anything new).

**No task regressed on `rrk@10` vs `base@10`** (all 18 rows identical at
K=10, mean 0.893 = 0.893) — consistent with `CONFIDENCE_REBUILD_FINDINGS.md`'s
finding that ranking-order effects concentrate at tight K, and with
passthrough being order-preserving so it can't remove anything a caller
would see in a K=10 window that confidence-ranking wouldn't already show.

**Retrieval-ceiling-limited, not fixable by ranking or rerank**
(`recall_at_all` bounds, from the underlying pool capture):
`multihop-04-mediatek-brands` (0.0 — GT never fetched) and
`multihop-06-advantech-cloud` (0.667 — 1 of 3 GT never fetched). Same
Q1/Q2 boundary `CONFIDENCE_REBUILD_FINDINGS.md` already drew: no downstream
ranking or rerank change can recover what retrieval never fetched.

### Improvements

4 tasks improve `rrk@gt` over `base@gt` with 1 regressing (matches
`CONFIDENCE_REBUILD_FINDINGS.md`'s "4 improved / 1 regressed" on its 17-task
set — same underlying signal, same tasks: `crosslang-05`, `crosslang-06`,
`multihop-02`, `multihop-03`). `multihop-06`, newly included here, neither
improves nor regresses (0.0/0.0 at `@gt`, 0.667/0.667 at `@10` — retrieval-
ceiling-limited either way).

---

## Verdict

**Confirmed by this run:**
- The `scoped_rerank` production wiring integrates cleanly with the
  confidence-ranked pool across all 18 tasks — no exceptions, no silent
  corruption, order-preserving and non-lossy when degraded (verified
  per-task, not asserted).
- The three-way comparison shows the same structural story
  `RETRIEVAL_CONFIDENCE_STRUCTURAL_PROBLEM.md` and
  `CONFIDENCE_REBUILD_FINDINGS.md` already established: Salva-current's gate
  (mean recall 0.382 over its 17 valid replays) trails both the ungated
  accumulate baseline (0.648) and confidence-ranked accumulate (0.744) by a
  wide margin. The gate is the bottleneck, not the rerank stage's presence or
  absence.

**NOT confirmed by this run — the actual gap for the next card:**
- Whether a *real* LLM call in `scoped_rerank` improves precision/filters
  noise beyond what confidence-ranking alone already does. Every rerank call
  in this run degraded to passthrough because this sandbox's omlx
  `/v1/chat/completions` endpoint returns HTTP 500 (server-side, confirmed
  via direct `curl`, independent of model or payload). `accumulate+rerank`'s
  numbers here are, by construction, identical to confidence-ranking-only
  numbers.

## Recommendation for `salva-p7-production-wire-rerank-mode`

**Not yet safe to make `admission_policy="rank"` + `scoped_rerank` the
default.** Safe as an **opt-in mode** — the wiring itself is proven clean and
the ranking-signal gain is real and already adopted per
`CONFIDENCE_REBUILD_FINDINGS.md`. But shipping it as *the* rerank pipeline
without ever having exercised a working LLM completion would mean shipping
an LLM-filtering feature that has literally never filtered anything in
validation — the noise-discarding behavior is the entire point of adding an
LLM stage over confidence-ranking alone, and it remains unverified past one
hand-run task with a different model (`multihop-01`, Haiku, in
`accumulate_llm_rerank.md`).

Before productionizing further: get one working LLM backend (fix the local
omlx `/v1/chat/completions` 500 — worth a separate infra ticket, it blocks
more than just this card — or point `scoped_rerank`'s `complete=` at a
reachable alternative for validation purposes) and re-run this exact script;
compare `rrk@gt`/`rrk@10` against this passthrough baseline to see whether
real LLM judgment adds precision without the corroboration-driven tight-K
regression already seen, or introduces new ones. That's a re-run of existing
tooling, not new design work.
