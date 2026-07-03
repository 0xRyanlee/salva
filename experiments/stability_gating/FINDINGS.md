# Stability Gating — A/B Findings

**Date:** 2026-07-03
**Status:** ⚠️ INCONCLUSIVE

## Hypothesis

`enable_stability_gating` / `StabilityPolicy` (opt-in, disabled by default) adjusts
`QualificationScorer` composite scores using a domain-level drift + volatility
signal computed from `query_family_memory` history. The claim under test:
turning it on produces a measurable, directionally sensible change in scoring
for a domain with real history, without being a no-op.

## Method

### Step 1 — existing history check

```
DEFAULT_DB_PATH: /Volumes/Astoria/Projects/salva/data/salva_runtime.db
total records: 2020
Counter({'bd_leads': 126, 'companies': 46, 'events': 19, 'partnerships': 9})
```

The default project DB already has 46 `companies`-domain records (well above
`min_history=3`). **We did not read from or write to this DB for the scoring
experiment** — see Isolation below for why.

### Step 2 — live retrieval attempt (3 calls, isolated project_id)

Ran `run_discovery()` three times with `execution.project_id="stability_eval"`
(routes persistence to `data/projects/stability_eval/salva.db`, not the
default DB) varying market/industry:

| Call | market/industry | raw_count | qualified_count | retrieval_health |
|---|---|---|---|---|
| 1 | Taiwan / semiconductor | 0 | 0 | probe_failed |
| 2 | Taiwan / AI hardware | 0 | 0 | probe_failed |
| 3 | US / semiconductor | 0 | 0 | probe_failed |

All three came back with `retrieval_health: "probe_failed"` and 0 raw
results — this sandbox has no outbound network access to SearXNG/DDG, as
expected per the task brief. The 6 `query_family_memory` rows these calls
still wrote (2 per call, into the isolated project DB) have `raw_total=0`,
`content_nodes=[]` — no real signal, unused in the analysis below. We
stopped after 3 live calls (well under the ~10 cap) rather than retrying
against a network path that clearly wasn't going to come up.

### Step 3 — seeded history (fallback, as instructed)

Directly inserted 5 realistic `query_family_memory` rows for domain
`"companies"` into a scratch SQLite DB (`/private/tmp/stability_eval_test.db`,
via `salva_core.persistence.db.get_conn(path=...)` — never touches the
default DB path). Rows simulate a real Taiwan-semiconductor company-research
thread with genuine topic drift across records (foundry → fabrication → IC
design → equipment → AI chips) and genuine `success_score` variance
(0.45–0.70), not placeholder text:

| query | content_nodes | success_score |
|---|---|---|
| Taiwan semiconductor foundry companies | semiconductor, taiwan, foundry, TSMC, chip manufacturing | 0.62 |
| Taiwan chip fabrication companies | semiconductor, taiwan, fabrication, UMC, wafer production | 0.58 |
| Taiwan IC design startups | IC design, taiwan, fabless, MediaTek, startup | 0.45 |
| Taiwan semiconductor equipment suppliers | semiconductor, equipment, taiwan, ASE, packaging testing | 0.70 |
| Taiwan AI chip companies | AI chip, taiwan, edge AI, GPU, neural processing | 0.51 |

`compute_stability_signals("companies", min_history=3, path=SCRATCH_DB)`
returned real (non-fabricated) output:

```
drift = 0.8542   (mean 1 - Jaccard across consecutive records — high, because
                   each record's content_nodes are a mostly-disjoint 5-term set)
volatility = 0.0866  (pstdev of success_score across the 5 records)
stability_score = max(0, 1 - min(1, drift + volatility)) = 0.0593
```

### Step 4 — scoring A/B

Called `QualificationScorer.score()` directly on 4 synthetic but realistic
`UnifiedResult` candidates (2 on-topic Taiwan semiconductor companies, 1
off-topic consumer blog with a hard negative-signal term, 1 more on-topic
company) against `Intent(domain="companies", ...)`, once with
`context={}` and once with `context={"w_stability": 0.15, "stability_score": 0.0593}`
(0.0593 is the real value from Step 3, 0.15 is `StabilityPolicy.penalty_strength`'s
default):

| candidate | score OFF | score ON | delta |
|---|---|---|---|
| TSMC foundry capacity expansion | 0.6867 | 0.6048 | −0.0819 |
| Taiwan fabless IC design startup | 0.7117 | 0.6266 | −0.0851 |
| "Top 10 gadgets" consumer blog (hard negative signal: "consumer") | 0.1000 | 0.1000 | 0.0000 |
| ASE packaging/testing expansion | 0.6242 | 0.5505 | −0.0737 |

Rank order (by score) was **identical** on vs. off:
`[IC design startup, TSMC, ASE, gadgets blog]` in both conditions.

Supplementary directional sanity check (not part of the primary A/B, single
candidate, synthetic `stability_score` values to confirm the mechanism moves
both directions): the same TSMC candidate scored 0.6867 with no stability
context, 0.6048 with our seeded domain's real (low) `stability_score=0.0593`,
and 0.7210 with a hypothetical high `stability_score=0.95`. Monotonic and in
the expected direction — low stability → penalty, high stability → boost.

## Isolation

- Live `run_discovery()` calls used `execution.project_id="stability_eval"`,
  which routes all persistence (via `get_db_path_for_project()`) to
  `data/projects/stability_eval/salva.db` — a path distinct from
  `DEFAULT_DB_PATH`. This is a product-native isolation mechanism, not an
  out-of-band workaround.
- Directly-inserted seed rows went into `/private/tmp/stability_eval_test.db`,
  a path with no relationship to the project at all.
- Verified default DB (`data/salva_runtime.db`) record count via
  `list_query_family_memory()`: **2020 records before this experiment, 2020
  after.** Untouched.
- One byproduct: `data/projects/stability_eval/salva.db` now exists (created
  by the 3 live-attempt calls) with 6 empty-content rows. It is not the
  default DB, contains no real signal (`raw_total=0` on every row), and was
  not read from in the scoring analysis. Left in place; harmless, but noting
  its existence for full disclosure.

## Verdicts

- **Does the signal move the score at all?** ✅ Yes — every non-hard-rejected
  candidate's score moved by roughly −0.07 to −0.09 in this run, and the
  supplementary check confirms the direction flips with a high
  `stability_score`. The wiring is not hollow.
- **Does it change ranking within a single domain's candidate set?** ❌ No,
  not in this test, and not by construction — `stability_score` is a single
  domain-level scalar, so it shifts every candidate's score in the same
  direction; it cannot reorder candidates that share a domain unless the
  shift happens to cross the `qualify_threshold` for some but not others
  (it didn't, in this N=4 sample — all qualifying candidates stayed well
  above `companies`' 0.40 threshold).
- **Does it interact with hard negative-signal rejection?** Notable
  mechanical detail: `QualificationScorer.score()` returns early
  (`signal_score * 0.3`) for any candidate matching a negative signal term,
  *before* the stability term is applied. Stability gating has zero effect
  on hard-rejected candidates.

**Overall: ⚠️ INCONCLUSIVE.** The mechanism is real and directionally
sensible, but N=4 candidates / 1 seeded domain / synthetic history is nowhere
near enough to say whether it helps, hurts, or is noise in production. See
below.

## Honest Observations

1. **This signal is domain-level, not per-node/per-candidate.** This is by
   explicit design (see `salva_core/stability.py` module docstring — Salva's
   persisted history only has multi-record, timestamped structure at the
   query-family/domain grain, not finer). Every result belonging to the same
   domain in the same request receives the identical `stability_score`
   adjustment. It is a domain-wide dial, not a per-result relevance signal.
2. **Live retrieval was attempted and failed cleanly, not silently.** All 3
   live `run_discovery()` calls returned `retrieval_health: "probe_failed"`
   with 0 raw/qualified results — this sandbox has no outbound network path
   to SearXNG/DDG. This matches the task brief's expectation and required no
   further troubleshooting; we did not retry beyond 3 calls once the pattern
   was clear.
3. **History was seeded, not live.** Because live retrieval produced nothing
   usable, the 5 history rows used for `compute_stability_signals()` were
   inserted directly into a scratch SQLite DB using realistic Taiwan-
   semiconductor company-research vocabulary (not "test1/test2"
   placeholders), with genuine record-to-record variation in both
   `content_nodes` (drift) and `success_score` (volatility) so the computed
   signal wasn't trivially 0. The resulting `drift=0.854`, `volatility=0.087`
   are real outputs of `compute_stability_signals()` over this seeded data —
   not invented numbers — but they describe an artificial history, not an
   organically-accumulated one.
4. **Isolation was achieved and verified**, not merely assumed — see
   Isolation section above, with before/after record counts on the default
   DB.
5. **Sample size is trivially small.** 4 candidates, 1 domain, 1 seeded
   history shape, `penalty_strength` only tested at its default (0.15). No
   claim here should be read as "stability gating improves precision/recall"
   — that would require live retrieval (unavailable in this sandbox) and a
   ground-truth-labeled benchmark, neither of which this experiment had.
6. **No percentage or improvement claims are made.** The only quantified
   claims are the specific delta values shown in the table above, which are
   direct tool output, not derived/extrapolated statistics.

## What This Proves

- The `w_stability` term is wired into `QualificationScorer.score()` and
  measurably moves scores when `context["w_stability"]` and
  `context["stability_score"]` are populated (i.e. the feature is not dead
  code / not silently a no-op when enabled).
- The direction is sane: low `stability_score` (volatile/drifting domain
  history) pulls scores down; high `stability_score` (stable history) would
  pull them up, holding `penalty_strength` fixed.
- `_apply_context()` renormalizes all scorer weights when `w_stability > 0`,
  so enabling this feature reallocates weight away from content/contact/
  signal/region/source/recency proportionally — it is not simply additive
  bonus/malus on top of the existing 1.0-weight composite.
- Hard negative-signal rejection short-circuits before the stability term is
  ever applied.

## What This Does NOT Prove

- Whether stability gating improves or degrades real discovery quality
  (precision/recall/lead relevance) — requires live retrieval, which was
  unavailable in this sandboxed environment.
- Whether a domain-level signal is the right grain, or whether the
  documented per-node/per-candidate limitation matters in practice for
  real query mixes.
- Whether the seeded history's drift/volatility values (0.854 / 0.087) are
  representative of real accumulated query-family memory, versus an
  artifact of the 5 hand-picked, deliberately-varied seed rows.
- Whether the observed −0.07 to −0.09 score deltas are large enough to
  matter given `qualify_threshold` in realistic result distributions with
  scores closer to the boundary than this sample's.
- Whether different `min_history` / `penalty_strength` values change the
  picture meaningfully — only the defaults (`min_history=3`,
  `penalty_strength=0.15`) were tested.
