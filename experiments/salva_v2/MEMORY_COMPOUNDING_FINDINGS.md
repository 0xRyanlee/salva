# Memory Compounding Findings — does query-family memory improve later rounds on live data?

**Date:** 2026-07-03
**Answer, upfront: no measurable effect observed.** Across all 4 domains
tested, memory on (`write_mode="quarantine"`) and memory off
(`write_mode="none"`) produced **identical `qualified_count` sequences** for
every round. VP9's claim that persistent memory compounding improves
retrieval is still unvalidated on live data — this is the third attempt
(after E9's synthetic-corpus PASS and E21's failed live attempt) and the
first one to actually isolate the memory variable cleanly, and it found
nothing.

## Why this test is different from prior VP9 attempts

- E9 validated VP9 mechanistically on a **synthetic/frozen corpus** — not
  live retrieval.
- E21 attempted live validation but **failed for an unrelated reason**
  (provider/retrieval issues, not the memory mechanism itself) per
  `DEVELOPMENT_PROGRESS.md`.
- `experiments/salva_v2/task_set_v1.json` (Phase 3's main task set) is
  **structurally incapable of testing compounding** — every one of its 18
  tasks is a one-shot query in a fresh domain; there is no "same domain,
  multiple rounds" scenario to compound over.

This is why `memory_taskset_v1.json` exists: 4 domains (TSMC, MediaTek,
CNCF, Advantech) x 3 sequential, thematically-evolving queries each
(identity -> competitive landscape -> partnership signals), all sharing one
`project_id` and `write_mode` per (domain, condition) pair so memory
genuinely has a chance to accumulate and feed forward within a domain.

## The experiment was verified to actually engage the memory mechanism

Before trusting a "no difference" result, checked whether `write_mode=
"quarantine"` was actually writing anything -- a silently-broken write path
would make "no difference between on/off" meaningless rather than a real
finding. Confirmed via direct sqlite query on the per-project databases:

| project_id | write_mode | `query_family_memory` rows after 3 rounds |
|---|---|---:|
| `memory-exp-on-tsmc` | quarantine | **20** |
| `memory-exp-off-tsmc` | none | **0** |

Memory genuinely was written in the "on" condition and genuinely was not in
the "off" condition -- the mechanism engaged as designed. The null result
below is real, not an artifact of a broken write path.

## Full results: qualified_count per round, memory on vs off

| domain | condition | round 1 (identity) | round 2 (competitors/parent-org) | round 3 (partnerships) |
|---|---|---:|---:|---:|
| tsmc | memory_on | 3 | 0 | 0 |
| tsmc | memory_off | 3 | 0 | 0 |
| mediatek | memory_on | 0 | 0 | 0 |
| mediatek | memory_off | 0 | 0 | 0 |
| cncf | memory_on | 0 | 0 | 0 |
| cncf | memory_off | 0 | 0 | 0 |
| advantech | memory_on | 0 | 0 | 0 |
| advantech | memory_off | 0 | 0 | 0 |

**Every single domain shows an identical sequence between memory_on and
memory_off.** Not "roughly similar" -- exactly identical, round by round.
Raw data: `experiments/salva_v2/raw_results_rerun/memory-{on,off}-{domain}.json`
(8 files).

## Round-2/3-vs-round-1 recall change (the core compounding metric)

Since qualified_count didn't move between conditions, there is no
compounding signal to report in either direction:

- **tsmc**: round 1 finds 3 qualified entities (all correctly identifying
  TSMC's official site/profile/stock listing); rounds 2-3 both regress to 0
  regardless of memory -- this looks like the same `DOMAIN_CONFIGS["market_
  intel"]`/`DOMAIN_CONFIGS["partnerships"]` signal-vocabulary gap already
  diagnosed in `RESCORE_COMPARISON.md` for round 2's `find_market_activity`
  objective and round 3's `find_partnership_signals` objective, not a
  memory effect either way.
- **mediatek / cncf / advantech**: all three rounds return 0 qualified
  entities regardless of memory, for all three domains. No baseline to
  compound from.

## Honest interpretation

This is **not** "memory compounding doesn't work" as a general claim -- the
sample here is too narrow and confounded by the same scoring-layer gaps
`RESCORE_COMPARISON.md` already documents (most rounds return zero qualified
entities before compounding even has anything to build on). What this
finding actually supports, precisely:

**VP9's claimed live-data compounding effect remains unobserved in every
real test attempted so far** (E21 failed for provider reasons; this test
isolated the memory variable cleanly and still found nothing). The
practical blocker is upstream of memory entirely: **a domain needs to
regularly produce qualified entities in round 1 before there's anything for
round 2+ to compound on.** Given `RESCORE_COMPARISON.md`'s finding that most
domains/objectives in this session's tests return `qualified_count: 0`, most
of this task set's rounds had no baseline signal to compound from in the
first place -- memory had nothing to work with, not because memory itself
is broken, but because the scoring layer is filtering out round 1's
candidates before memory-relevant signal (content_terms, source authority)
ever accumulates.

## What would actually test VP9 properly

Not carded here (out of this card's scope), but the logical next step once
`DOMAIN_CONFIGS["partnerships"]`/`["market_intel"]`'s signal-vocabulary gap
(flagged in `RESCORE_COMPARISON.md`) is addressed: re-run this exact
`memory_taskset_v1.json` protocol once round 1 reliably produces qualified
entities across all 4 domains, so there's an actual non-zero baseline for
round 2/3 to compound against. Testing memory compounding on a system whose
scoring layer usually returns nothing is testing the wrong variable.

## Guardrails honored

No memory-mechanism code was modified in this card -- `write_mode="none"`
vs `"quarantine"` is an existing, already-implemented policy switch
(`salva_core/schemas.py::MemoryPolicy`), used exactly as designed. Ground
truth in `memory_taskset_v1.json` is either reused from `task_set_v1.json`'s
already-verified research (same session) or freshly researched via
WebSearch with cited sources for the 4 new "competitors"/"parent
organization" queries -- no fields were LLM-generated without verification.
