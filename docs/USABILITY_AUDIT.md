# Usability Audit — real data, post Phase 1-4

**Date:** 2026-07-03
**Status:** Audit only, no code changed. Findings below, each with a
priority. Concrete fixes are separate future cards, not implemented here.

This supersedes an earlier session's fable-based usability analysis, which
was written before Phase 1's topology-degradation bug was fixed and before
any real benchmark data existed. Every finding below is backed by either
direct code inspection with file:line references, or a live measurement
taken in this session — not carried over from that earlier speculation.

## 1. Sync (`salva_discover`) vs async (`salva_job_create`) split — guidance is calibrated on the wrong variable

**Current guidance** (`apps/mcp/server.py::salva_discover` docstring):
"Use this for quick, focused searches (max_results ≤ 20). For larger or
background runs use `salva_job_create` instead." The decision rule is
**output size** (`max_results`), not wall-clock latency.

**Measured live** (this session, not from Phase 3's raw data — Phase 3
never actually captured `latency_seconds` despite `EXPERIMENT_PROTOCOL.md`
listing it as a metric to record; confirmed via `grep` across all 62
raw_results/raw_results_rerun files, 0/62 have it — flagging this as its
own honest gap in the earlier experiment, not glossed over):

| query shape | max_results | rounds | elapsed |
|---|---:|---:|---:|
| simple company lookup, 3 rounds needed | 10 (default) | 3 | **19.65s** |
| partnership query, exits early (nothing to expand) | 10 (default) | 2 | 5.29s |
| single-round company lookup | 10 (default) | 1 | 4.28s |

A default-sized (`max_results=10`, well under the "≤20" sync threshold),
completely normal 3-round query took **~20 seconds** synchronously. That's
within most HTTP/MCP client timeout budgets (typically 30-60s) but not
comfortably so — a query needing more rounds, or hitting a slow/degraded
provider, could plausibly cross into timeout territory while still
qualifying as "quick" by the documented `max_results` rule.

**Priority: medium.** Not broken today, but the guidance rule (output
size) doesn't track the thing that actually matters for a sync call
(wall-clock time). A future fix could either (a) add an actual latency
budget/timeout parameter to `salva_discover` with a documented default, or
(b) change the docstring's decision rule to something latency-aware
(e.g. "route to async whenever `experience_profile` resolves to
`deep_investigation`," since multi-round routes are the ones likely to run
long).

## 2. `retrieval_health` covers the topology probe only, not the actual retrieval rounds — a real blind spot, not a false alarm

Traced precisely via code, not inferred: `retrieval_health` is computed
exactly once, inside `_apply_live_probe()` (`salva_core/topology.py:36`),
which runs a lightweight **pre-check probe** (historically SearXNG-backed,
per this session's Phase 1 fix) *before* the actual multi-round retrieval
begins. It is never touched again after that point — `salva_core/service.py:202`
just copies `topology_plan.retrieval_health` straight into `meta`.

Meanwhile, `execute_discovery()` DOES collect a richer signal that never
reaches the caller: `_collect_source_attempts(retrievers)`
(`salva_core/service.py:179`) builds per-provider attempt records (which
provider, succeeded or not, error message) — but `run_discovery()`'s public
return signature is a 4-tuple `(entities, relations, telemetry, meta)`
(`salva_core/service.py:100`); the 5th internal value (`source_attempts`)
is used only to persist the run to the DB (`salva_core/service.py:109`) and
to compute a bare **count** in `meta["source_attempt_count"]`
(`salva_core/service.py:190`) — the per-provider success/failure detail
itself is discarded from the direct return value.

**And even that count doesn't reach an MCP caller.** `apps/mcp/server.py::
salva_discover`'s JSON response (lines 159-179) hand-picks a subset of
`meta` -- `run_id`, `entity_count`, `qualified_count`, `rounds`, `domain`,
`memory_seeds_used`, `retrieval_health`, `execution` -- `source_attempt_count`
is not among them.

**Concrete failure scenario this creates**: topology probe succeeds
(`retrieval_health: "ok"`), then every actual retrieval-round provider
(whoogle/marginalia/ddgs/searxng_pool) times out or errors during the real
search. The MCP caller sees `retrieval_health: "ok"` — a **false-positive
health signal** — with the only visible sign of trouble being
`qualified_count: 0`, which is indistinguishable from "genuinely found
nothing" (the same signature as most of this session's scorer-layer
findings in `RESCORE_COMPARISON.md`). The two failure modes ("infra
degraded" vs "scoring rejected everything") are currently unobservable from
outside the process.

**Priority: high.** This is exactly the kind of silent-degradation bug
Phase 1's topology fix addressed for the probe path specifically — the
same class of problem still exists one layer deeper, for the actual
retrieval rounds. A caller (agent or human) genuinely cannot currently tell
"Salva's infrastructure had a bad day" apart from "there was nothing to
find" apart from "the scorer rejected good candidates" (per
`RESCORE_COMPARISON.md`) — three very different situations that all look
identical from outside.

## 3. Hold's REST surface is richer than `DEVELOPMENT_PROGRESS.md` claims -- but MCP parity is the real gap

`DEVELOPMENT_PROGRESS.md`'s Known Gaps list (item 4, referenced by this
card's own background) claims Hold C1/C2 "只有 `hold_walk` 一個入口" (only
has one entry point, `hold_walk`). **Verified via direct grep against
`apps/api/main.py` — this claim is stale/inaccurate.** There are 8 distinct
`/v1/hold/*` REST endpoints today: `/schema`, `/schema/entities`,
`/schema/relations`, `/migrations`, `/storage`, `/backends`, `/views`,
`/views/{view_name}`, plus `/walk` itself — a materially richer REST
surface than the "one entry point" characterization suggests. Worth
correcting in a future doc-hygiene pass, though that's a small, separate
fix from this audit's own finding below.

**The real gap found here is different: none of that REST surface is
exposed via MCP tools.** Grepped `apps/mcp/server.py` for any
Hold-related tool definitions — zero matches. The closest thing,
`salva_graph_export`, covers exporting a single run's graph (HIF/DOT), not
the schema/backends/views/migrations endpoints. Since this project's own
README frames MCP as "推薦 — Agent 首選" (recommended, agent's first
choice), an agent working through the recommended primary interface
currently cannot introspect Hold's schema, available backends, or named
views at all — only a REST caller can.

**Priority: medium.** Not urgent (these are introspection/discovery
endpoints, not core retrieval functionality), but a real, verified
parity gap between the "recommended" interface and what's actually
possible via REST. Also flags the `DEVELOPMENT_PROGRESS.md` claim itself as
needing a correction in a future doc pass -- not fixed here (out of this
card's scope).

## 4. Headless/library-import callers: `retrieval_health` visible, but with the same probe-only caveat as #2 -- and they get MORE diagnostic detail than MCP callers, not less

Tested directly, not assumed -- this session ran `run_discovery()` as a
plain Python import dozens of times without going through MCP or an agent
at all, and `meta.get("retrieval_health")` was consistently present and
readable every time. So for a headless/library caller, the signal *is*
visible -- same probe-only scope limitation as finding #2, but at least not
additionally hidden behind an MCP response's curated field subset.

**A real asymmetry worth noting**: a headless caller gets the *entire*
`meta` dict (`topology_confidence`, `source_pack`, `strategy_bias`,
`fanout_policy`, `merge_policy`, `probe_queries`, `experience_notes`, etc. --
see the full list at `salva_core/service.py:182-213`), while
`salva_discover`'s MCP JSON response exposes only a hand-picked subset.
This means a Python-import caller currently has *better* observability
into what Salva actually did than the "recommended" MCP path does -- the
opposite of what you'd expect from an agent-first interface. Not
necessarily wrong (some of that detail is genuinely internal/noisy), but
worth an explicit decision on which fields the MCP response *should*
surface, rather than the current ad hoc subset.

**Priority: low.** Nothing is silently broken for headless callers; this
is a design-coherence observation, not a defect.

## Summary table

| # | Finding | Priority | Fix scope (not done here) |
|---|---|---|---|
| 1 | Sync/async split guidance uses output size, not measured latency (~20s observed for a "quick" 3-round query) | Medium | Add latency-aware routing guidance or a timeout param |
| 2 | `retrieval_health` only covers the topology probe, not actual retrieval-round provider failures; `source_attempts` detail is collected but discarded before reaching any caller | **High** | Extend the health signal (or expose `source_attempt_count`/detail) to cover the real retrieval rounds, at both the Python-return and MCP-JSON layers |
| 3 | Hold REST surface (8 endpoints) has no MCP parity; `DEVELOPMENT_PROGRESS.md`'s "only hold_walk" claim is stale | Medium | Add MCP tools for the missing Hold endpoints agents actually need; separately correct the stale doc claim |
| 4 | Headless callers see more of `meta` than MCP callers do -- an inverted-from-expected observability gap, not a broken one | Low | Deliberate decision on what `salva_discover`'s JSON should surface |

No API/MCP schema was modified in this card -- audit and findings only,
per this card's guardrail.
