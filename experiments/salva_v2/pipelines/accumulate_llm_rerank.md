# Pipeline variant: accumulate raw candidates, one-shot LLM filter/rerank

**Status:** methodology + validated on 1 task (see "Validation run" below).
Not yet run at full comparison scale — that's
`experiments/salva_v2/pipelines/BASELINE_VS_VARIANTS_FINDINGS.md`.

## Hypothesis being tested

Salva's current pipeline gates every candidate through
`processing/scorer.py::QualificationScorer.score()` round-by-round, using
hand-tuned per-domain keyword lists (`DOMAIN_CONFIGS`). `RESCORE_COMPARISON.md`
found this gate is the actual bottleneck for several domains — not because
retrieval failed (`retrieval_health` was `ok` throughout), but because the
keyword vocabulary doesn't match how real content is phrased (e.g.
"strategic alliance"/"MOU" language doesn't appear in "which companies
were CNCF's founding members" content, which just states facts).

This variant tests a different design: **keep Salva's existing multi-round
retrieval + KeywordGraph query expansion exactly as-is (still the same
machinery, same providers), but remove the mechanistic per-round scoring
gate entirely, accumulate every raw candidate across all rounds, and defer
all filtering/relevance-judgment/reranking to a single LLM call at the
end** — closer to how a human researcher would actually work (search
broadly, then read and judge what's actually useful), and something an LLM
is arguably better suited to than a fixed keyword list.

## No new core code needed — verified, not assumed

`salva_core/schemas.py::DiscoveryRequest.qualify_threshold` (a `float | None`
field, see `salva-p35-scorer-threshold-wiring`) already provides exactly
the knob needed. Verified directly by calling `run_discovery()` with
`qualify_threshold=0.0`:

```python
req = DiscoveryRequest(objective="find_partnership_signals",
                        intent=DiscoveryIntent(market="Global", industry="cloud native / open source",
                                                extra_keywords=["CNCF founding members", "Cloud Native Computing Foundation", "2015"]),
                        qualify_threshold=0.0)
entities, relations, telemetry, meta = run_discovery(req)
# raw_count: 21, qualified_count: 21, entity_count: 21
```

Because the composite scoring formula (`processing/scorer.py`'s
`0.25*content_match + 0.20*contact_completeness + 0.20*signal_strength +
0.15*region_match + 0.10*source_trust + 0.10*recency`) is built entirely
from non-negative, `min(1.0, ...)`-clamped components, every candidate's
`relevance_score >= 0.0` is always true — so `qualify_threshold=0.0`
reliably surfaces **every non-duplicate raw candidate** as an "entity" via
the existing public API, with zero changes to `core/controller.py` or
`processing/scorer.py`. This variant is a pure experiment-script technique
layered on an existing knob, not new product code.

## Method

1. Call `run_discovery(DiscoveryRequest(..., qualify_threshold=0.0))` for
   the task — this runs Salva's real multi-round retrieval/extraction/dedup
   pipeline unmodified, just without the scoring gate, and returns every
   surviving raw candidate as an entity (title, source_urls, description/
   snippet available via `.model_dump()`).
2. Serialize the full raw candidate list (not summarized/truncated) plus
   the task's original intent (market/industry/objective/keywords) into a
   single prompt.
3. Spawn a Haiku Agent (`model: "haiku"`) with that prompt, instructing it
   to: identify which candidates are genuinely relevant to the question,
   discard the rest, deduplicate near-identical entries, and output a final
   ranked entity list in the same `{"name", "url", "claim"}` shape Phase 3's
   `reported_entities` used — so it can be scored against `task_set_v1.json`
   ground truth with the exact same method already established.
4. No further Salva involvement after step 1 — steps 2-3 are pure
   prompt/LLM work, run once per task (not per round).

## Rerank prompt template — v1 (superseded, see v2 below)

```
You are filtering and ranking raw search candidates for a business
research question. Some candidates are genuinely relevant; many are noise
(unrelated pages that happened to match a keyword).

Question: {question}
Original search intent: market={market}, industry={industry}, objective={objective}, keywords={keywords}

Raw candidates found by an automated multi-round search (unfiltered --
judge each on its merits):
{full list of candidates: title | url | snippet, one per line}

Task: identify which of these candidates are genuinely relevant and
useful for answering the question above. Discard irrelevant/noise
candidates. Merge near-duplicate entries referring to the same entity.
Output your final answer as a list of {"name", "url", "claim"} entries,
each with a one-sentence claim justifying why it answers the question.
If none of the candidates are relevant, say so honestly rather than
forcing a match.
```

## Rerank prompt template — v2 (fixes the precision gap v1 exposed)

`BASELINE_VS_VARIANTS_FINDINGS.md`'s comparison round found v1's one real
failure (`multihop-01`, see below) came from finalizing an answer straight
off a secondary-source summary (Wikipedia) without cross-checking it
against a primary source — not from insufficient search permission (v1
already allowed supplemental search; the agent simply judged the secondary
source "sufficient"). v2 adds one explicit instruction closing that gap:

```
[... same question/intent/candidates block as v1 ...]

Task: identify which of these candidates are genuinely relevant/useful.
Discard irrelevant/noise candidates.

IMPORTANT verification requirement: for factual claims like "who were the
founding members" of an organization, secondary/summary sources (Wikipedia,
blog aggregators) are known to sometimes repeat inaccurate or outdated
lists that don't match the organization's own original announcement.
Before finalizing your answer, you MUST cross-verify any such list against
the organization's OWN original announcement/primary source (search for
it directly) -- do not finalize an answer sourced only from a secondary
summary without this verification step, even if the secondary source
seems to answer the question.

Output your final answer as {"name", "url", "claim"} entries. Explicitly
state whether you performed the primary-source cross-verification and
what it changed, if anything.
```

**Validated on the exact case v1 failed** (2026-07-04, `multihop-01-cncf-
founders`, same 21-candidate raw pool as v1's validation run): the v2
prompt fetched CNCF's own June 21, 2015 press release and correctly
reported the full 22-member founding roster, explicitly identifying and
excluding RX-M (the same December-2015 joiner v1 wrongly included) and
naming all 10 members Wikipedia's summary had omitted (AT&T, Box, Cloud
Foundry Foundation, Cycle Computing, eBay, Goldman Sachs, Joyent, Kismatic,
Switch SUPERNAP, Weaveworks). This now matches the bare-agent baseline's
answer quality exactly, while still starting from Salva's own raw
retrieval pool rather than searching independently from scratch --
closing the one concrete gap `BASELINE_VS_VARIANTS_FINDINGS.md` identified,
with a single, targeted prompt change rather than new retrieval
infrastructure. **v2 is now the recommended prompt for this pipeline going
forward** -- v1 is kept above for the historical record of what the
comparison round actually tested, not because it's still preferred.

## Validation run (1 task) — real result, not the outcome expected going in

Ran end-to-end on `multihop-01-cncf-founders` (2026-07-04) — the same task
where Salva's normal pipeline returns `qualified_count: 0` and where the
bare-agent baseline (`baseline_multiround.md`) independently produced a
strong, correctly-sourced 22-member answer with the founding-vs-later
distinction intact.

**Step 1 output** (`qualify_threshold=0.0`): 21 raw candidates surfaced.
The pool is genuinely mixed — real signal (`Cloud Native Computing
Foundation - Wikipedia`, `Members - CNCF`) buried among 19 candidates of
unrelated noise (Chinese-language pages about the letter "W", a `CapCut`
download page, an unrelated business park in Chongqing, a German car-rental
forum).

**Step 2-3 output, actually run (not assumed)**: the Haiku rerank agent
**correctly discarded all 19 noise candidates and kept exactly the 2
genuinely relevant ones** — proving the noise-filtering half of this
hypothesis works. But its final answer only reported the **abbreviated,
commonly-miscited 13-name list** (Google, CoreOS, Mesosphere, Red Hat,
Twitter, Huawei, Intel, RX-M, Cisco, IBM, Docker, Univa, VMware) sourced
from the Wikipedia summary — the same imprecise list the bare-agent
baseline explicitly identified and corrected past (RX-M is actually a
December-2015 joiner, and the list omits AT&T, Box, Cloud Foundry
Foundation, Cycle Computing, eBay, Goldman Sachs, Joyent, Kismatic, Switch
SUPERNAP, Weaveworks). The agent's own notes say the CNCF Members page
"only shows present-day members rather than an explicit 2015 founding-
member list" and it did not go further to find CNCF's own original July
2015 press release.

**This is a genuinely important, non-obvious finding, not a clean win**:
this variant's answer quality is capped by what Salva's own retrieval
rounds actually fetched into the pool. The rerank LLM can only judge and
select from what's already there — it has no ability to go fetch a
better primary source if the retrieval rounds' query formulation never
surfaced one (Salva's rounds here found a Wikipedia summary and a
present-day-only CNCF members page, never CNCF's own historical press
release, which is exactly what the bare-agent baseline found on its own by
searching more specifically). **The bottleneck this specific case exposes
isn't "the scoring gate is too strict" (this variant removes that gate
entirely) — it's that the retrieval rounds themselves under-fetch relative
to what a freely-searching agent does.** That's a different, arguably more
fundamental finding than what this variant set out to test, and the
comparison card needs to carry this forward rather than treat "noise
filtering works" as the whole story.

Confirmed: the method works end-to-end (raw dump → LLM filter produces a
usable, real, sourced answer, and correctly separates signal from heavy
noise) — that's the property needed before running this at comparison
scale. But on this one task, it did NOT match the bare-agent baseline's
answer quality, despite matching or beating Salva's own current pipeline
(which returns nothing at all here). Whether this pattern holds across
more tasks, and whether it's specifically a retrieval-round query-
formulation gap rather than a scoring-gate gap, is exactly what the
comparison card needs to establish — not assumed from one task.
