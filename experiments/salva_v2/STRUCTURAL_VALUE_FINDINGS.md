# Structural Value Findings — does `pilot`/`audit`/route selection actually work?

**Date:** 2026-07-03
**Scope:** exploratory, 5 fresh runs (not the full 18-task scale) covering both
known-weak (`find_partnership_signals`, multihop-flavored) and known-strong
(`find_companies`, crosslang-flavored) query shapes, chosen to span the full
quality range Phase 3 already established. Runs made with persistence
enabled so real `run_id`s exist for `salva_audit`/`salva_pilot` to operate
on (`build_audit_report()`/`build_pilot_advice()` called directly, same
"call the underlying function" pattern used throughout this session's
experiments — not literal MCP wire calls).

**Headline: mixed.** `audit` is a real, useful signal. Route selection is
systematic and sensible but doesn't predict outcome quality. `pilot`'s
tested suggestions did not produce a real improvement — the one case that
looked like an improvement was a false positive.

## Test runs

| task | objective | qualified_count | route | topology |
|---|---|---:|---|---|
| multihop-01-cncf-founders | find_partnership_signals | 0 | deep_investigation | semantic_union |
| multihop-06-advantech-cloud | find_partnership_signals | 0 | deep_investigation | semantic_union |
| crosslang-01-tsmc | find_companies | 5 | company_research | vertical |
| crosslang-05-chunghwa | find_companies | 7 | company_research | vertical |
| single-04-mediatek | find_companies | 0 | company_research | vertical |

## 1. `audit` — real signal, correlates with known outcome quality

`salva_audit`'s `metrics.avg_score`/`metrics.qualified_rate`/`notes` cleanly
separated the 3 known-bad runs from the 2 known-good runs, with no manual
adjustment needed:

| task | qualified_count | avg_score | qualified_rate | notes |
|---|---:|---:|---:|---|
| multihop-01 | 0 | 0.1465 | 0.0 | low_qualified_rate, high_noise_rate, weak_source_reliability, no_plugin_activity |
| multihop-06 | 0 | 0.0514 | 0.0 | low_qualified_rate, high_noise_rate, weak_source_reliability, no_plugin_activity |
| single-04-mediatek | 0 | 0.0663 | 0.0 | low_qualified_rate, high_noise_rate, weak_source_reliability, no_plugin_activity |
| crosslang-01-tsmc | 5 | 0.5007 | 0.8333 | weak_source_reliability (only) |
| crosslang-05-chunghwa | 7 | 0.6120 | 1.0 | weak_source_reliability (only) |

**Verdict: audit's score genuinely tracks real quality in this sample.**
Every known-bad run scored below 0.15 avg_score and got the
`low_qualified_rate`/`high_noise_rate` flags; every known-good run scored
above 0.5 and got neither flag. If a caller used `audit` to triage which
runs need a re-query without knowing the ground truth in advance, this
sample suggests it would correctly flag the bad ones. Caveat: n=5, not a
large-scale validation — but this is a real, positive, mechanism-level
finding, not just an impression.

## 2. Route selection — systematic, but doesn't predict success

Route/topology assignment is not random or cosmetic: `find_partnership_
signals` queries consistently routed to `deep_investigation` +
`semantic_union` topology, while `find_companies` entity-lookup queries
consistently routed to `company_research` + `vertical` topology. This is a
real, observable, sensible categorization by query *type*.

**But route choice does not predict outcome quality.** `company_research`
route succeeded for 2/3 tested cases (crosslang-01, crosslang-05) and
failed for the third (single-04-mediatek, same route, same topology,
qualified_count=0). `deep_investigation` route failed for both cases
tested. Route selection correctly recognizes *what kind* of question is
being asked, but the scorer-layer signal-vocabulary gap already documented
in `RESCORE_COMPARISON.md` dominates the actual outcome regardless of which
route gets picked -- routing to the "right" strategy doesn't rescue a query
whose domain's scoring config doesn't have matching vocabulary.

## 3. `pilot` — tested suggestions did not improve results; one "improvement" was a false positive

`salva_pilot`'s primary output is not "the one best next query" -- its
richest field is actually `clarifying_questions` (e.g. "precision vs
coverage?", "time window?", "focus axis?"), meant to be answered by a human
or agent before the next round runs. It does also return a `next_queries`
list (3 candidates for both tested runs), which is what this card's own
framing assumed pilot would provide, so that's what was tested directly.

For `multihop-01-cncf-founders` (round 1: qualified_count=0), pilot
suggested 3 next queries. Ran each as a fresh `run_discovery()` call:

| pilot-suggested next query | qualified_count | verdict |
|---|---:|---|
| "Global cloud native / open source CNCF founding members Cloud Native Computing Foundation" (mechanical concatenation of the original intent fields) | 0 | no improvement |
| `"Global"` (a bare quoted region string -- looks like a degenerate suggestion, not a real query) | *(not run -- not a meaningful query to test)* | -- |
| "Global partner sponsor collaboration" | **1** | **false positive, not a real improvement** -- see below |

For `multihop-06-advantech-cloud` (round 1: qualified_count=0), the
analogous first suggestion ("Global industrial IoT cloud platform Advantech
IIoT") also stayed at qualified_count=0.

**The one nominal improvement was a false positive.** The single qualified
entity from "Global partner sponsor collaboration" was:

> "Partner with us — Global Alliance" (globalalliancepr.org/partner-with-us,
> confidence 0.3693)

This is a PR-industry trade association's generic partnership page --
completely unrelated to CNCF founding members. The vague, generic phrasing
of this pilot suggestion (itself likely a byproduct of the same
signal-vocabulary gap diagnosed in `RESCORE_COMPARISON.md`, not a pilot-
specific bug) pulled in an unrelated entity that happened to match generic
partnership vocabulary. A wrongly-qualified answer is arguably *worse* than
staying at 0 and honestly reporting nothing found.

**Verdict: no evidence pilot's tested suggestions improve real outcomes.**
Small sample (2 runs, 3 total suggestions tested), so this doesn't prove
pilot is *never* useful -- but on the concrete cases tested here, following
its next-query suggestions either changed nothing or introduced a false
positive. This is a genuine negative finding, reported as such rather than
softened.

## Summary for the PRD positioning decision

This file is one of the key inputs the `docs/product-brief.md`
"⚠️ 待 owner 拍板" section calls for:

- **`audit`**: real, working, positive evidence (n=5, directionally clean).
- **route selection**: real and sensible as a query-classification
  mechanism, but does not by itself predict or improve outcome quality.
- **`pilot`**: no positive evidence from this test; one concrete negative
  data point (a suggested query produced a false positive). Needs either
  more testing at larger scale or a fix (e.g. the generic/mechanical
  next_queries phrasing) before it can be cited as a working differentiator.

No pilot/audit/route code was modified for this card -- black-box
verification only, per this card's own guardrail.
