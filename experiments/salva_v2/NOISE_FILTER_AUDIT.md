# Noise Filter Audit — crosslang-06-delta's "high_noise_rate" case

**Date:** 2026-07-03
**Verdict: no systemic problem found.** The noise-filtering layers
(prefilter/dedup/scorer) worked correctly in this case. What actually
happened is more mundane and arguably healthy system behavior: ambiguous
raw retrieval + a correctly-triggered honesty signal, not noise leaking
through a broken filter.

## What the original run actually showed

`experiments/salva_v2/raw_results/crosslang-06-delta_B.json`'s own notes
field (written by the Phase 3 Arm B agent) says Salva "surfaced unrelated
memory-seed suggestions (Beam Tech Electronics, Compal, Cincon, C-Media,
BXB)" and that "Salva's own feedback/pilot block flagged
`needs_clarification=true` and `high_noise_rate`". `ANALYSIS_FINDINGS.md`
summarized this as "Salva returned unrelated noise for crosslang-06-delta_B
and flagged its own high_noise_rate/needs_clarification signals" -- grouped
alongside genuine zero-contribution cases as one of the session's clean
failure examples.

## Investigation

Started from the card's own hypothesis (prefilter/dedup/scorer let
something through) and followed the actual evidence instead of assuming
that hypothesis was correct.

**Step 1 -- checked whether "memory-seed suggestions" is literal.** Read
`salva_core/service.py::_seed_graph_from_memory()` (line 285) and
`core/keyword_graph.py::KeywordGraph.seed_from_memory()` (line 109).
Confirmed: `MemoryPolicy.read_scope` defaults to `"none"`
(`salva_core/schemas.py:266`), and `_seed_graph_from_memory` returns `0`
immediately when `read_scope == "none"` -- no seeding happens unless a
caller explicitly opts in. The original Phase 3 Bash command for this task
used a plain `DiscoveryRequest(...)` with no `execution`/`memory` override,
so `read_scope` was at its default `"none"`.

**Step 2 -- reproduced the exact query 3 times** (once with the original
Phase 3 wording, twice more with slight variants) via direct
`run_discovery()` calls, checking `meta["memory_seeds_used"]` explicitly.
**All 3 reproductions show `memory_seeds_used: 0`.** No cross-contamination
from prior runs' query-family memory occurred -- the seeding mechanism
correctly stayed off.

**Step 3 -- inspected live `telemetry.reject_reasons` and `noise_domains`**
across the reproductions. Raw retrieval genuinely did return tangential/
irrelevant content for this ambiguous Chinese-keyword query (`v.qq.com`
Tencent video pages, a French SFR telecom community forum, a Malaysian tech
forum in one reproduction; near-empty results in another) -- but **every
single candidate was correctly rejected with `low_signal`, and
`qualified_count` was 0 in every reproduction.** Nothing wrongly qualified.

## Conclusion: which layer "let this through"? None did.

Re-characterizing what actually happened, layer by layer:

1. **Retrieval**: genuinely noisy/tangential raw results for this specific
   ambiguous query -- this is a live-search characteristic (already
   disclosed and expected per `EXPERIMENT_PROTOCOL.md`'s non-goals), not a
   Salva bug.
2. **Prefilter/dedup**: not directly implicated -- the noise reached the
   scorer stage (visible in `reject_reasons`), so it passed through these
   earlier stages, but that's fine because...
3. **Scorer**: correctly rejected 100% of the noisy candidates as
   `low_signal`. `qualified_count: 0` in every run. Nothing noisy was ever
   presented as a qualified answer.
4. **`high_noise_rate`/`needs_clarification` telemetry**: this is Salva
   *correctly self-reporting* that it couldn't find confident matches for
   this query, rather than confidently returning a wrong answer. This is
   the system doing the right thing, not a failure mode.

**The original hypothesis that memory-seed cross-contamination was the
culprit was investigated and ruled out** by reading the actual seeding code
and confirming via 3 reproductions that seeding stayed off, consistent with
the default `read_scope="none"`. The Phase 3 agent's own "unrelated
memory-seed suggestions" phrasing was an inaccurate gloss on ordinary raw
retrieval noise, not a literal description of the
`_seed_graph_from_memory()`/`seed_from_memory()` code path -- worth
correcting for anyone reading that note going forward, though it doesn't
change any actual system behavior.

## Was `ANALYSIS_FINDINGS.md`'s characterization wrong?

Slightly overstated, not wrong on the core fact. "Salva actively returned
noise" is technically accurate about what candidates were *considered*
internally, but reads as implying the noise reached the final answer --
it didn't (`qualified_count: 0`, same as most other multihop tasks in that
analysis). A one-line clarifying note has been added to
`ANALYSIS_FINDINGS.md` pointing here, without rewriting the original
finding (per this session's established convention of not silently editing
prior conclusions).

## No fix implemented

Per this card's explicit guardrail ("如果稽核發現這只是單一個案...在完成備註
裡誠實說明「這不是系統性問題」，不用勉強生出修復"): no code change is
warranted here. The layers that should catch noise did catch it correctly.
There is nothing to patch in prefilter, dedup, or the scorer's
`noise_domains`/`trusted_sources` for this specific case -- inventing a fix
for a system that already worked correctly would be solving a problem that
doesn't exist.

This is a different (narrower) finding than `RESCORE_COMPARISON.md`'s
signal-vocabulary/trusted_sources gap for the `partnerships`/`market_intel`
domains -- that is a real, confirmed calibration gap causing false
*negatives* (correct candidates wrongly rejected). This audit's case is the
opposite direction (candidates that deserved rejection, correctly
rejected) and found no defect.
