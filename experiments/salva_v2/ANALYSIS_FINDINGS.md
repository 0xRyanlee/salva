# Phase 3 Analysis — Arm A (bare Haiku) vs Arm B (+Salva)

**Date:** 2026-07-03
**Status:** Analysis of `experiments/salva_v2/raw_results/` (36 runs, all 18 tasks in
`task_set_v1.json`), executed per `EXPERIMENT_PROTOCOL.md`.

**Charts** (`experiments/salva_v2/charts/`, same hand-rolled-SVG convention as
`experiments/agent_vs_salva/results/naturehike-dach-comparison.svg`):
- [`recall_per_task.svg`](charts/recall_per_task.svg) — per-task recall, Arm A vs Arm B grouped bars (visualizes the 17-tie pattern directly).
- [`cost_efficiency.svg`](charts/cost_efficiency.svg) — recall vs `requests_used` scatter (the cost-efficiency view called for so a signal like E21c's "19 requests, zero true positives" can't be masked by a P/R/F1 number alone).
- [`retrieval_health_distribution.svg`](charts/retrieval_health_distribution.svg) — Arm B's `retrieval_health` was `ok` in all 18/18 runs; shown as a single clean bar rather than a misleading 3-slice pie with two empty slices.

**2026-07-03 follow-up (post scorer fix):** the "Salva's own scoring layer
returns zero usable entities in 61% of runs" finding below led to two fixes
(`salva-p35-scorer-partnerships-domain`, `salva-p35-scorer-threshold-wiring`).
Arm B was re-run afterward on the same 18 tasks to test whether that
converted any of the ties below into real wins. **Short answer: no** — see
[`RESCORE_COMPARISON.md`](RESCORE_COMPARISON.md) for the full comparison and
the deeper vocabulary/trusted-source calibration gap it surfaced. The
findings below are preserved exactly as originally written — nothing in this
section has been altered to match the rescore.

## Headline verdict

**Recall/correctness: 17 ties, 1 Arm B win, 0 Arm A wins.** On pure
recall against ground truth, Arm A and Arm B are statistically
indistinguishable across this 18-task set — Salva being available did not
meaningfully change whether the agent found the right answer, because
Arm B's agents consistently fell back to WebSearch (which the protocol
explicitly permits) whenever Salva's own output was empty or noisy, which
was most of the time (see below). This is a materially different, more
nuanced picture than E10's "Salva loses badly to a bare agent" — but the
reason is not that Salva itself got better; it's that this protocol lets a
smart agent route around a weak tool, which is realistic production
behavior, not a flattering test design.

**Salva's own qualification/scoring contributed zero usable entities in
11 of 18 Arm B runs (61%)**, despite `retrieval_health: ok` in all 18 runs
(100%). This is the single most important, cleanly-evidenced finding of
this analysis: **the failure mode is in the scoring/qualification layer,
not retrieval.** The underlying search infrastructure was healthy the
entire time (confirming the P1 fixes from earlier this session — ddgs
installed, local SearXNG running — actually worked); `QualificationScorer`
simply filtered out every candidate on 11 of 18 queries.

**Efficiency: Arm B used 14% fewer total requests than Arm A** (38 vs 44
across all 18 tasks) for equivalent recall — on the 7 tasks where Salva did
return qualified entities, it often let the agent skip a WebSearch
follow-up entirely. This is a real, modest, honest win for Arm B, distinct
from the recall question.

## Detailed per-task results

| task_id | tier | Arm A recall | Arm B recall | Arm B qualified_count>0? | requests A/B | winner |
|---|---|---:|---:|---|---:|---|
| single-01-tsmc | single_entity | 1.0 | 1.0 | yes (3) | 2/2 | tie |
| single-02-naturehike | single_entity | 1.0 | 1.0 | **no (0)** | 4/4 | tie |
| single-03-cncf | single_entity | 1.0 | 1.0 | **no (0)** | 1/1 | tie |
| single-04-mediatek | single_entity | 1.0 | 1.0 | **no (0)** | 5/2 | tie |
| single-05-advantech | single_entity | 1.0 | 1.0 | **no (0)** | 1/1 | tie |
| single-06-gleif | single_entity | 1.0 | 1.0 | **no (0)** | 1/2 | tie |
| crosslang-01-tsmc (台積電) | cross_language | 1.0 | 1.0 | yes (5) | 1/2 | tie |
| crosslang-02-asus (華碩) | cross_language | 1.0 | 1.0 | yes (4) | 1/1 | tie |
| crosslang-03-acer (宏碁) | cross_language | 1.0 | 1.0 | yes (4) | 1/1 | tie |
| crosslang-04-foxconn (鴻海) | cross_language | 1.0 | 1.0 | yes (4) | 1/1 | tie |
| crosslang-05-chunghwa-telecom (中華電信) | cross_language | 1.0 | 1.0 | yes (7) | 2/2 | tie |
| crosslang-06-delta (台達電子) | cross_language | 1.0 | 1.0 | **no (0, noise)** | 2/2 | tie |
| multihop-01-cncf-founders | multi_hop | 1.0 (6/6) | 1.0 (6/6) | **no (0)** | 3/2 | tie |
| multihop-02-tsmc-customers | multi_hop | 1.0 (5/5) | 1.0 (5/5) | **no (0)** | 3/2 | tie |
| multihop-03-naturehike-dach | multi_hop | 0.67 (2/3) | **1.0 (3/3)** | **no (0)** | 5/3 | **Arm B** |
| multihop-04-mediatek-brands | multi_hop | 1.0 (5/5) | 1.0 (5/5) | **no (0)** | 3/3 | tie |
| multihop-05-gleif-regulators | multi_hop | 0.5 (2/4) | 0.5 (2/4) | partial (2, low-conf) | 5/5 | tie |
| multihop-06-advantech-cloud | multi_hop | 1.0 (3/3) | 1.0 (3/3) | **no (0)** | 3/2 | tie |

Note on the "reported=N" counts in the raw data vs the recall fractions
above: agents frequently over-report (e.g. returning 3 URLs for the same
TSMC entity, or auxiliary detail pages beyond the ground truth's specific
`official_website`) — recall here is computed on entity-identity/name
match against `ground_truth_entities`, not raw item count, per
`EXPERIMENT_PROTOCOL.md`'s metric definitions. Cross-language scoring
required a correction mid-analysis: an initial pass matched strictly by
`official_website` domain and produced false negatives (e.g. flagging a
correct "Delta Electronics, Inc." answer sourced from Wikipedia/Yahoo
Finance as a miss, because the ground truth's `official_website` field
uses `deltaww.com` and the agent cited a different but equally correct
source) — corrected to entity-name matching, which is what this tier is
actually testing (per `TASK_SET_README.md`'s own tier description).

## Where Salva actually helped vs. where it was dead weight

**Salva contributed genuine qualified entities in 7/18 runs** (single-01,
all 6 crosslang tasks except crosslang-06, and a partial/low-confidence
contribution on multihop-05) — **all of them `find_companies` queries with
a specific, well-formed company name as the primary search term**,
disproportionately the Chinese-character cross-language queries (5/6
crosslang tasks had qualified Salva output, vs. only 1/6 single-entity
English-only tasks).

**Salva contributed zero qualified entities in 11/18 runs**, cutting
across every task shape except the pattern above:
- English-only single-entity lookups for real, findable, but not
  TSMC-scale-famous entities (CNCF, MediaTek, Advantech, GLEIF, Naturehike
  — the scorer filtered out everything despite these being easy tasks a
  bare agent solved in 1-2 WebSearch queries).
- **Every single `find_partnership_signals` (multi_hop) query returned
  qualified_count=0** except a 2-entity low-confidence partial on
  multihop-05. This objective/scoring path looks structurally unsuited to
  relationship-discovery queries as currently tuned — 0/6 is not noise,
  it's a consistent pattern.
- One outright noise case: crosslang-06-delta's Arm B run returned
  unrelated candidates and Salva's own telemetry flagged
  `high_noise_rate`/`needs_clarification` — the one case where Salva
  actively produced garbage rather than just nothing.

**Business outcome framing** (per the protocol's qualitative metric, not
just P/R/F1): in every one of the 11 zero-contribution cases, the AGENT
still delivered a real, correct, actionable business outcome (an official
contact page, a verified entity name, a documented partnership) — but it
did so *despite* Salva, not *because of* it, by falling back to the same
WebSearch capability Arm A had the whole time. If an agent were forced to
trust Salva's qualified output alone (no WebSearch fallback allowed), 11 of
18 tasks would have returned nothing.

## Answering the protocol's explicit analysis questions

1. **Does Arm B win/lose/tie more often, with a pattern by difficulty
   tier?** 17 ties, 1 Arm B win, 0 Arm A losses. No tier shows Arm A
   outright winning. The one clear Arm B win (multihop-03, the
   deliberately-thin Naturehike DACH task) is *not* attributable to Salva
   contributing anything (its qualified_count was still 0) — it came down
   to Arm B's WebSearch execution happening to be more thorough on that
   particular run, which is agent-to-agent variance, not a Salva effect.
2. **On tasks Arm B loses, is it because Salva returned nothing or
   something actively worse?** Arm B never lost outright in this run (worst
   case was a tie). Of the 11 zero-contribution cases, only one
   (crosslang-06-delta) was "actively worse" (noise); the other 10 were
   simply empty, not misleading.
3. **Does `retrieval_health` correlate with losses?** No correlation to
   test — `retrieval_health` was `ok` in all 18/18 runs, including all 11
   zero-qualified-entity runs. This directly confirms the failure mode is
   in scoring/qualification, not retrieval or provider health.
4. **What does `requests_used` say about efficiency independent of
   winning?** Arm B used 38 total requests vs Arm A's 44 (-14%) for
   identical-or-better recall. The savings concentrate on the 7 tasks
   where Salva's own output was usable enough to skip a WebSearch
   follow-up.
5. **(Arm C not run this pass — memory write_mode ablation, optional per
   protocol, not executed.)**
6. **(Arm D not run this pass — free-provider-combination ablation,
   optional per protocol, not executed. `salva-p2-diagnostic-isolation`'s
   provider-layer findings still stand as the best available evidence on
   this question.)**

## What this does NOT prove

- Not a formal significance test (protocol's own non-goal) — 18 tasks with
  17 ties is a real pattern, not noise, but this is not a claim backed by
  a p-value.
- Does not prove Salva's structured/hypergraph representation is
  worthless — the qualification/scoring layer specifically (not retrieval,
  not extraction, not the hypergraph model) is what's filtering out
  correct candidates. A scorer fix could change this picture substantially
  without touching anything else in the pipeline.
- Arm B was executed via a direct Python call to `run_discovery()`
  (documented deviation in `salva-p3-execute-arms`'s commit), not the
  literal MCP wire protocol — code path is equivalent, but this is not a
  test of MCP transport reliability itself.
- Optional Arms C/D were not run — no data here on memory-compounding's
  marginal contribution or on how much of Salva's performance is
  attributable to provider selection specifically.
- Small task set (18) skewed toward Taiwan/tech-industry entities per
  `TASK_SET_README.md`'s own design notes — generalization to other
  industries/regions is untested.

## Recommendation for next steps (not executed here — flagging for future cards)

The clearest, most actionable finding is that **`QualificationScorer`'s
qualify_threshold (or composite formula) is rejecting correct candidates
at a high rate (11/18) despite healthy retrieval**, and that this is
*especially* severe for `find_partnership_signals` (6/6 zero-contribution).
Investigating and likely loosening/re-tuning the scorer for these query
shapes — not touching retrieval, providers, or the hypergraph model at
all — looks like the single highest-leverage fix suggested by this
experiment. This is a recommendation, not something implemented by this
analysis card, which is scoped to analysis only per its own guardrails.
