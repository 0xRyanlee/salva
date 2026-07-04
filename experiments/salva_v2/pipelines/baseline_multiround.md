# Baseline: N-round bare agent multi-round retrieval (Arm 0)

**Status:** methodology + prompt template. Validated on 2 sample tasks
(see "Validation run" below). Not yet run at full comparison scale — that's
`experiments/salva_v2/pipelines/BASELINE_VS_VARIANTS_FINDINGS.md`.

## Why this exists (distinct from Phase 3's Arm A)

Phase 3's `EXPERIMENT_PROTOCOL.md` Arm A gave a Haiku agent a single
question and a budget of "up to 5 WebSearch queries" with no explicit round
structure — it was a reasonable bare-search control for the "does Salva's
retrieval beat nothing" question, but it does not model what a real user
means by "multi-round retrieval": explicit rounds, each round informed by
what was found in the previous one, explicit accumulation across rounds.

This harness fixes that: **N explicit rounds, each one aware of everything
accumulated so far**, with no Salva involvement at all. This is the
baseline every future pipeline variant (accumulate+LLM-rerank, future
DOM-simulation variants, hypergraph-driven variants, etc.) gets compared
against — defined once here, reused every time, not re-invented per
experiment.

## Structure

- `max_rounds = 3` (matches `core/types.py::Intent.max_rounds`'s own default
  of 3, for comparability against Salva's own round budget).
- Each round: up to 3 WebSearch queries (9 total across 3 rounds — close to
  `EXPERIMENT_PROTOCOL.md`'s original 5-per-task Arm A budget, but spread
  across explicit rounds instead of one flat budget).
- Round 1: agent decides the query itself from the task's intent fields,
  with no prior context.
- Rounds 2-3: agent is shown **everything accumulated in prior rounds**
  (every result found so far, not just a summary) and must decide, on its
  own, what this round should search for — to fill a gap, verify an
  ambiguous candidate, or expand in a new direction. No Salva concepts
  (routes, hypergraph, query-family memory) are mentioned anywhere in this
  prompt — this is deliberately the "just an agent with a search tool"
  condition.
- After the final round, the agent must produce its answer purely from the
  accumulated pool across all rounds — not just the last round's results.

## Prompt template

Round 1:
```
You are researching a business question, using up to 3 rounds of web
search (up to 3 WebSearch queries per round). This is round 1 of 3.

Question: {question}

Decide what to search for in this first round. After searching, report:
(a) what you found this round (title/url/snippet for each result),
(b) what you still don't know / what's uncertain,
(c) what you'd want to search for in round 2 and why.
```

Round N (2 or 3), given round N-1's full transcript:
```
You are continuing a multi-round research task. This is round {N} of 3.

Question: {question}

Everything found so far (rounds 1..{N-1}):
{full accumulated results from all prior rounds, not a summary}

Decide what this round should search for, based on what's still missing or
uncertain from the above -- do not re-search things you've already found
confidently. After searching, report:
(a) what you found this round,
(b) whether you now have enough to answer, or what's still missing.
```

Final round only, additional instruction appended:
```
This is the final round (3 of 3). After this round's search, give your
final answer based on everything accumulated across all 3 rounds --
report each entity/fact with its source URL.
```

## Recording format

Per task, one JSON file:
```json
{
  "task_id": "...",
  "arm": "baseline_multiround",
  "rounds": [
    {"round": 1, "queries_used": 2, "new_results": [{"title": "...", "url": "...", "snippet": "..."}]},
    {"round": 2, "queries_used": 3, "new_results": [...]},
    {"round": 3, "queries_used": 1, "new_results": [...]}
  ],
  "total_requests_used": 6,
  "final_reported_entities": [{"name": "...", "url": "...", "claim": "..."}]
}
```

## Validation run (2 tasks, confirming the prompt actually produces multi-round behavior)

Ran this exact 3-round structure via a Haiku Agent (2026-07-04) on
`multihop-01-cncf-founders` (a task the current Salva pipeline fails on,
per `RESCORE_COMPARISON.md`) and `crosslang-01-tsmc` (a task it succeeds
on), to confirm before committing to the full comparison that the prompt
genuinely produces round-aware behavior rather than front-loading
everything into round 1. Real transcripts, not paraphrased:

- **multihop-01-cncf-founders**: genuine round-to-round adaptation.
  Round 1 found CNCF's July 2015 founding announcement (22 organizations).
  Round 2 and 3 specifically chased down a subtlety worth flagging on its
  own: several *secondary* sources (Wikipedia-derived summaries, blog
  posts) repeat an abbreviated "13-name" founding list that actually
  **mixes true July-2015 founders with at least one December-2015 joiner
  (RX-M)** and omits several real founders (AT&T, Box, Cloud Foundry
  Foundation, Cycle Computing, eBay, Goldman Sachs, Joyent, Kismatic,
  Switch SUPERNAP, Weaveworks). The agent caught this discrepancy itself
  by cross-checking CNCF's own two press releases (July vs December 2015)
  and reported the full, correctly-sourced 22-name roster with the
  founding-vs-later distinction explicit. **Worth naming directly: this
  bare-agent baseline produced a materially better answer for this task
  than Salva's own pipeline has ever produced** (which returns
  `qualified_count: 0` for this exact task in every run this session,
  per `RESCORE_COMPARISON.md`) — a concrete data point for the comparison
  card to reckon with, not just a prompt-validation footnote.
- **crosslang-01-tsmc**: round 1 resolved the entity with high confidence
  (Taiwan Semiconductor Manufacturing Company Limited) but also surfaced a
  same-sounding-domain trap (`taiwansemi.com`, an unrelated power-
  semiconductor company). Round 2 explicitly said round 1 already
  resolved identity with high confidence and pivoted to disambiguating
  that domain trap plus a stock-ticker cross-check, instead of repeating
  the identity search. Round 3 pivoted again to verifying current (not
  stale annual-report-PDF) contact details directly from tsmc.com. This
  is genuine round-aware prioritization, not 3 independent single-shot
  searches wearing a "round" label.

Confirmed: the prompt structure produces real round-to-round adaptation,
which is the property this harness needs before it's trustworthy as a
baseline. Full-scale comparison against pipeline variants is the next
card's job — but the CNCF result above is already a meaningful early
signal worth carrying into that comparison, not dismissing as "just
validation."
