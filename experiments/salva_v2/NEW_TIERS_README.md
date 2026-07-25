# Task Set — New Tiers — Design Notes & Ground Truth Verification Method

`task_set_new_tiers.json` — 12 additional tasks across 3 new difficulty tiers
(`n_ary_relational`, `aggregation_count`, `negative_absence`), on top of
`task_set_v1.json`'s existing `single_entity` / `cross_language` / `multi_hop`
(18 tasks, 6 each).

## Why this exists

Source: owner's response (2026-07-25) to `salva-positioning-single-fact-vs-relational`
— rather than picking option A (declare single-fact lookup out of scope, narrow
the benchmark to n-ary GT) or B (keep current scope, chase bare-agent parity),
the owner asked for the benchmark itself to be broadened first, "不論有沒有利
都該有參考" (more reference data regardless of which way it cuts), before that
positioning decision gets re-opened. See board card
`salva-benchmark-expand-task-types-reference`.

This file adds task TYPES the existing set didn't cover, rather than more
tasks of the same shape:

| Tier | What it tests | Why the existing tiers don't cover it |
|---|---|---|
| `n_ary_relational` | One relation tying **3+ named parties together** (a corporate family, an SEC acting-in-concert group) | `multi_hop` asks "who are members/customers of X" — a list of independent facts about X, satisfiable with partial recall. These tasks require the **full member set of one hyperedge-shaped fact**; a subset answer is a materially different (wrong) fact, not partial credit. This is the closest proxy in this benchmark to Salva's own claimed differentiator (`hg_penetration`'s acting-in-concert hyperedge). |
| `aggregation_count` | "How many X does Y have, broken down how" | Existing tiers ask for named facts/entities, never a count derived by synthesizing a set. Getting the count right while inventing a plausible wrong breakdown (or vice versa) is a distinct failure mode from either single-fact lookup or relation enumeration. |
| `negative_absence` | Correctly reporting **explicit, reasoned absence** of a fact, not fabricating one | Round 2 (`ROUND2_FINDINGS.md`) flagged `multihop-03-naturehike-dach`'s low-confidence-by-design case as a scoring concern for exactly this failure mode, but no task in the existing set has a clean, unambiguous negative ground truth with a specific, verifiable reason. These four tasks do. |

## Ground truth verification method — different from, and stricter than, `TASK_SET_README.md`'s

`TASK_SET_README.md` verifies via live WebSearch against a cited source URL.
This worker session had no WebSearch/WebFetch tool available, only `curl`/Python
`urllib` — so instead of guessing at search results, ground truth here is
sourced entirely from **live, public, machine-readable registry APIs**:

- **GLEIF LEI API** (`api.gleif.org`) — the Legal Entity Identifier system;
  `direct-children`/`ultimate-children`/`direct-parent-reporting-exception`
  endpoints return an entity's legally-reported corporate-family and
  parent-relationship facts as structured JSON, keyed by a globally unique,
  regulator-assigned LEI. No search, no ambiguity about "which page is
  official" — the LEI record IS the primary source.
- **SEC EDGAR** (`efts.sec.gov` full-text search + `sec.gov/Archives` filing
  documents) — the same real SC 13D/A filing (Chatham Lodging Trust /
  BlueMountain group, accession `0001193125-13-424143`, 2013-11-04)
  descriptively referenced in `experiments/hg_penetration/README.md`, but
  **independently re-fetched and re-parsed for this task** (not copied from
  that experiment's prose claim uncritically) — see `nary-04`'s `notes` field.

This is arguably a **stricter** standard than the existing tiers': every
`source_url` in this file is a live API/document endpoint that can be
re-fetched to get the exact same structured answer back, not a webpage whose
content or existence could change. `harness/validate_new_tiers.py --live`
automates that re-fetch and diffs it against the stored JSON (see below) —
something the WebSearch-based tiers can't easily do, since search results
aren't stable/replayable the way a versioned registry API is.

## Honest caveats (same discipline as `TASK_SET_README.md`)

1. **GLEIF re-publishes its "golden copy" snapshot periodically.** The
   `direct-children`/`ultimate-children` membership lists in `nary-01..03`
   and `agg-01..04` are point-in-time (golden-copy `publishDate` observed as
   `2026-07-25T08:00:00Z` during verification, 2026-07-26). Real-world
   mergers, new registrations, or LEI lapses can change these lists — re-run
   `harness/validate_new_tiers.py --live` before relying on this set for a
   high-stakes comparison, not just once at authoring time.
2. **GLEIF registry participation ≠ real-world corporate structure.**
   `agg-04-advantech-subsidiary-count-edge-zero`'s "0 subsidiaries" is a fact
   about which entities have an LEI-registered `direct-parent` link back to
   Advantech — Advantech almost certainly has real-world subsidiaries that
   simply aren't required to (or haven't) registered that relationship in
   GLEIF. This is called out explicitly in the task's own `notes` field so a
   grader doesn't score "Advantech literally has zero subsidiaries" as the
   intended reading.
3. **Reason-code prose definitions are recalled, not re-fetched.** The four
   `reason_code` values in `negative_absence` (`NO_KNOWN_PERSON`,
   `NON_CONSOLIDATING`, `NON_PUBLIC`, `NATURAL_PERSONS`) are live-fetched and
   exactly reproducible via each task's `source_url`. Their plain-language
   definitions in each task's `notes` field are recalled from general
   knowledge of GLEIF's standard Level 2 reporting-exception reason list, not
   independently re-verified against GLEIF's own CDF specification document
   this session (that page returned a redirect during verification, not a
   fetchable spec page) — marked `confidence: medium` on the paraphrase
   specifically, separate from the `high`-confidence live-fetched code itself.
4. **This does not resolve the A/B positioning question by itself.** These
   12 tasks give the eventual re-run of `salva-positioning-single-fact-vs-relational`
   more surface area to reason from (relational-but-not-2-hop, aggregation,
   and honesty-under-absence, on top of the existing single-fact/cross-lang/
   multi-hop tiers) — they do not by themselves prove Salva does better or
   worse than a bare agent on any of these tiers. That requires actually
   running the pipeline against this set (out of scope for this card; see
   `EXPERIMENT_PROTOCOL_ROUND2.md`/`round2_runner.py` for the harness pattern
   an eventual Round 3 would extend).
5. **Scope was capped deliberately, not exhaustively.** 4 tasks per new tier
   (12 total) rather than 6 to match the existing tiers exactly — every task
   here required an independent live API round-trip to source and verify (no
   templated padding), and 4 well-verified tasks per tier with genuinely
   distinct distractor shapes (see e.g. `agg-01` vs `agg-02`'s different
   jurisdiction-bucket shapes, or the four distinct `reason_code`s in
   `negative_absence`) was judged more useful than 6 with a duplicated shape.
   A `temporal_change` tier (testing Salva's cross-run compounding-memory
   differentiator, E9) was considered and deferred — GLEIF's API surfaces
   current state, not historical point-in-time snapshots, and building a
   reliable point-in-time ground truth without a search tool was judged too
   time-constrained to do without padding out weak evidence. Flagged here so
   it isn't silently dropped from consideration; a follow-up card could pick
   it up specifically if the positioning decision wants that axis covered too.

## How to audit/extend this task set

- Re-verify any entry: fetch its `source_url` directly, or run
  `python -m experiments.salva_v2.harness.validate_new_tiers --live` to
  re-check every GLEIF/SEC fact in this file against the live API in one pass.
- To add a new task to these tiers, or a new tier: follow the same three-part
  discipline as `TASK_SET_README.md` — (1) design the query/intent against a
  real `DiscoveryIntent`/`DiscoveryRequest`, (2) verify ground truth against a
  live, structured, re-fetchable source (not a one-off search result), (3)
  report honestly when evidence is thin or a count is an artifact of registry
  scope rather than real-world fact, the way `agg-04`'s notes do.
- Do not silently edit `ground_truth_entities` without updating `source_url`/
  `confidence`/`notes` to match, same rule as the existing task set.
