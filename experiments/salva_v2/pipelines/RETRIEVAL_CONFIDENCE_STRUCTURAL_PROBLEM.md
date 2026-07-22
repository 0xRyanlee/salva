# Structural problem statement: retrieval query formulation + confidence/cleaning layer

**Date:** 2026-07-10
**Why this file exists:** owner directive — the empirical, case-by-case pipeline
experiments (`BASELINE_VS_VARIANTS_FINDINGS.md`, `accumulate_llm_rerank.md`)
found real results but kept fixing one symptom at a time. Owner wants the
underlying problem abstracted structurally once, handed to an independent
model pass (fable) for diagnosis, that diagnosis code-verified against the
actual codebase, then a final feasible solution proposed — not another
one-off prompt tweak. This file is the input to that first fable pass.

## What is already established, not hypothesis (cite, don't re-derive)

1. **Gate mechanism, not vocabulary, is the bottleneck** —
   `BASELINE_VS_VARIANTS_FINDINGS.md`. On the 6 hardest (`multihop`)
   tasks in `experiments/salva_v2/task_set_v1.json`, Salva's own scored
   pipeline (`processing/scorer.py::QualificationScorer`, gated per-round on
   hand-tuned `DOMAIN_CONFIGS` keyword lists) returns `0/26` ground-truth
   entities even though `retrieval_health` reports `ok` throughout. Setting
   `qualify_threshold=0.0` (removing the gate, keeping retrieval identical)
   and adding a single end-of-run Haiku LLM rerank pass raises recall to
   `~24/26`. This directly falsifies the prior hypothesis
   (`RESCORE_COMPARISON.md`) that the problem was signal-vocabulary/
   trusted-source miscalibration for the `partnerships` domain — that fix
   was applied and made no measured difference on rerun.

2. **The gate's replacement (LLM rerank) has its own ceiling, already
   identified, not yet solved** — `accumulate_llm_rerank.md`'s validation
   run (`multihop-01-cncf-founders`). The rerank step correctly discarded
   19/21 noise candidates (proving relevance-judgment generalizes better
   than a keyword list), but its final answer was capped by what Salva's
   own multi-round retrieval had fetched into the pool: a Wikipedia summary
   citing an imprecise, commonly-miscited 13-name list, never CNCF's own
   original 2015 press release with the correct 22-name roster. The
   bare-agent baseline found the primary source because it could search
   further on its own; the rerank pass could only judge what was already
   fetched. A v2 prompt (explicit "cross-verify against primary source"
   instruction) fixed this **one specific case** after the fact — it is a
   prompt patch, not a structural fix to retrieval's query formulation.

3. **This was flagged as a real, separate, unsolved lever** —
   `BASELINE_VS_VARIANTS_FINDINGS.md`'s own "Recommended next iteration"
   section: *"the clearest next move is not another rerank-prompt tweak,
   but attacking the retrieval query-formulation gap"* — i.e., whether
   Salva's own `KeywordGraph` query expansion and multi-round strategy are
   formulating queries well, independent of the gate/no-gate question. This
   has not been tested. The comparison so far only varied gate vs no-gate,
   holding retrieval formulation constant.

4. **The current confidence/cleaning model is a flat, hand-tuned linear
   weighting, not a principled confidence estimate** —
   `processing/scorer.py`'s composite score:
   `0.25*content_match + 0.20*contact_completeness + 0.20*signal_strength
   + 0.15*region_match + 0.10*source_trust + 0.10*recency`, each term
   `min(1.0, ...)`-clamped and non-negative, thresholded per-domain via
   `DOMAIN_CONFIGS`. It was designed as a per-round admission gate, not as
   a confidence signal meant to survive gate removal. When the gate is
   removed (`qualify_threshold=0.0`), *every* candidate becomes an "entity"
   with no meaningful confidence ordering left — the LLM rerank pass is
   currently the only thing doing relevance judgment, in one un-scoped
   all-or-nothing call over the entire raw pool, with no signal about
   which candidates the *retrieval layer itself* considers well-sourced vs.
   likely noise, and no signal about whether the retrieval rounds
   themselves believe they've exhausted the sources worth trying.

## The two structural questions this file hands to the independent analysis

These are the owner's own framing of what's underneath the case-by-case
findings above — treat as the actual brief, not just decoration:

**Q1 — Tooling / experiment design**: is the current retrieval architecture
(provider fan-out, `KeywordGraph` query expansion, multi-round strategy in
`core/controller.py`) *itself* well-formulated, independent of scoring? The
CNCF case shows it can systematically under-fetch primary sources relative
to what a freely-searching agent finds. Is this a query-generation problem
(the queries themselves don't target primary-source phrasing), a
round-budget problem (not enough rounds/breadth), a provider-coverage
problem, or something else — and what would a structural fix look like
(vs. one more per-case prompt patch)?

**Q2 — Cleaning / confidence**: what should replace the current flat
hand-tuned `DOMAIN_CONFIGS` scoring formula as a principled way to (a) rank
candidate confidence for the downstream LLM judge (rather than a binary
gate or an all-or-nothing dump), and (b) signal noise/exhaustion —
i.e., let the pipeline (or the LLM judging it) know when it has likely
seen enough vs. when the pool is thin and more retrieval is warranted?

## Constraint carried over from the whole project

No paid tools/APIs — retrieval/embedding/LLM must stay on the existing free
self-hosted stack (local SearXNG/DDG/Marginalia/Whoogle providers,
sqlite-vec, Claude Code's own Haiku allotment). A structural fix must work
within this, not assume a paid reranker/embedding API.

## What this file does NOT ask for

Not another single-case prompt patch. Not a decision on Salva's product
positioning (that is a separate, parallel track — see
`salva_epistemic_hypergraph_framework.md` / owner directive 2026-07-10: the
evidence-preservation/context-compiler direction proceeds *in parallel*
with this retrieval-quality track, not instead of it).
