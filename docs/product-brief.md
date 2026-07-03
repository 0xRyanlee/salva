# Salva Product Brief

Salva is a self-hosted discovery intelligence runtime. It is not a one-off search tool or a scraper wrapper. It combines retrieval, routing, hypergraph structure, evidence, memory, auditing, and tenant boundaries into a reusable system.

This document is an introduction, not a PRD and not a canonical contract. For stable behavior, see `docs/spec/`.

## Positioning

- Built for agents, CLI, MCP, SDK, and REST callers
- Starts from structured intent
- Uses experience profiles to choose the retrieval path
- Compounds signal across multi-round retrieval and graph expansion
- Uses query-family memory so later runs get better
- Turns runs into a walkable hypergraph of entity, relation, evidence, and source data

## ⚠️ Owner decision needed: positioning claims vs Phase 3 measured data

The "Why It Beats Direct Search" and "Comparison Matrix" sections below were
written before the 2026-07-03 Phase 3 controlled experiment (18 fixed tasks,
`experiments/salva_v2/ANALYSIS_FINDINGS.md`). Phase 3's core findings:

- **Raw find-the-right-answer ability**: Arm A (bare Claude Code + Haiku) vs
  Arm B (+Salva) across all 18 tasks was **17 ties, 1 Arm B win, 0 Arm A
  wins** — not because Salva is more accurate, but because the agent was
  allowed to fall back to bare search whenever Salva underperformed, which
  is realistic production behavior, not a flattering test design.
- **Salva's own qualification/scoring layer returned zero usable entities
  in 61% (11/18) of test runs**, despite `retrieval_health` being `ok` in
  100% of runs — the bottleneck is `QualificationScorer`'s scoring logic,
  not retrieval or provider health.
- The "3 local comparison samples" cited in the "Effect Comparison" section
  below are from an earlier, much smaller, separate test (no verified
  ground truth) — not the Phase 3 dataset, and should not be read as
  corroborating it.

The practical tension this creates: this document currently positions Salva
as a strictly more-effective replacement for direct search, but Phase 3's
actual evidence supports something closer to "ties a bare agent on raw
answer-finding, with a real efficiency edge on some scenarios (Chinese-
keyword entity queries)" rather than blanket superiority. Options below are
left for the owner to decide — this pass does not rewrite the positioning
language on its own:

- **Option 1 — Keep the current positioning** (replaces/beats direct
  search): not supported by current Phase 3 data unless a larger follow-up
  experiment, or a fix to `QualificationScorer`'s filtering plus a re-test,
  produces stronger evidence.
- **Option 2 — Reposition as a "structuring/compounding layer"** (a value-
  add on top of direct search, not a replacement): better supported by
  Phase 3 — the route/pilot/audit/hypergraph/memory claims were not tested
  by Phase 3 at all (and not refuted either), and Arm B does have a real,
  modest efficiency win (14% fewer total requests). Under this framing,
  "Why It Beats Direct Search" would need to be rewritten around what
  structure Salva adds, not implied superiority at finding answers.
- **Option 3 — Narrow the effectiveness claims**: claim only what Phase 3
  data clearly supports (Chinese-keyword company lookups, cost efficiency),
  and honestly label other scenarios (single English-entity lookups,
  multi-hop relationship queries) as "ties bare search, pending a
  scoring-layer fix and re-test."

Full data: `experiments/salva_v2/ANALYSIS_FINDINGS.md` (includes 3 charts).

## Spotlight Features

- **Smart routing**: not every query follows the same path. Salva chooses between `quick_scan`, `lead_focus`, `company_research`, `deep_investigation`, and `platform_integrator`.
- **Multi-tool fan-out**: when signal quality is weak, Salva can expand across multiple providers and merge results.
- **Deep investigation**: Salva is not limited to the first answer. It uses `pilot`, `mate`, and `audit` to drive the next round and quantify value.
- **Hypergraph retention**: runs leave behind entity, relation, evidence, and hyperedge structure that can be walked later.
- **Compounding memory**: query-family memory makes later runs more targeted instead of starting from zero every time.

## Highlights

### 1. It compounds instead of only answering once

Most search tools answer “what did I find this time?” Salva also answers:

- which route should run
- what the next search step should be
- which sources are most useful
- whether this class of query gets better with repetition

That makes it a workflow, not just an endpoint. For a vibecoder or a non-expert operator, the model is simple: ask the system how to attack the problem, let it execute, then use the result as the starting point for the next round.

### 2. Agent-friendly decision surface

Salva exposes a clear index layer:

- `GET /v1/routes`
- `POST /v1/experience-plan`
- `POST /v1/pilot`
- `GET /v1/providers/catalog`
- `GET /v1/hold/backends`
- `GET /v1/semantic/indexes`

An agent can inspect the system before choosing a path.

### 3. Structured outputs

Salva returns:

- entities
- relations
- telemetry
- evidence
- run meta
- job state

That makes it closer to a research runtime than a search wrapper.

### 4. Built-in tenant, quota, and error contracts

The system already includes:

- tenant scope
- usage telemetry
- quota / rate-limit
- HTTP / MCP / job error contracts

This makes it suitable for team use, not just personal scripts.

### 5. It is a workflow base, not a single tool

Think of Salva as this sequence:

1. pick a route
2. run retrieval
3. inspect evidence
4. use `pilot` for the next round
5. let `hold` / semantic memory / audit preserve what was learned

That is the main difference from a regular API or CLI.

## Feature Summary

### Retrieval

- `POST /v1/discover`
- `POST /v1/jobs`
- `GET /v1/routes`
- `POST /v1/pilot`
- `POST /v1/mate/{run_id}`

### Observability

- `GET /v1/usage`
- `GET /v1/quota`
- `GET /v1/audits/{run_id}`
- `GET /v1/snapshots/{run_id}`
- `GET /v1/relations`

### Graph and memory

- `GET /v1/hold/backends`
- `GET /v1/hold/walk`
- `GET /v1/semantic/indexes`
- query-family memory

### Route modes

- `quick_scan`: one-pass fast answer
- `lead_focus`: narrow first, then expand
- `company_research`: balanced recall and structure
- `deep_investigation`: deeper exploration, more rounds
- `platform_integrator`: contract-first, downstream consumer friendly

### Integration

- MCP
- CLI
- Python SDK
- REST API

## How to Use It

### 1. Fast lookup

Use this for a single pass and quick qualification.

```json
POST /v1/discover
{
  "objective": "find_leads",
  "intent": {
    "market": "Germany",
    "industry": "software"
  },
  "max_results": 20,
  "output_profile": "lead"
}
```

### 2. Background research

Use jobs when you need multiple rounds and more signal.

- call `POST /v1/jobs`
- poll `GET /v1/jobs/{id}`
- then call `POST /v1/pilot`

### 3. Route first, then run

If the caller does not know the best path, inspect:

- `GET /v1/routes`
- `POST /v1/experience-plan`

That is more stable than pushing a large prompt directly.

### 4. For a full research topic

Use this pattern:

- run `find_market_activity` or `find_companies`
- feed the output into `POST /v1/pilot`
- inspect relations with `GET /v1/hold/walk`
- use `GET /v1/audits/{run_id}` and `POST /v1/mate/{run_id}` to decide whether to continue

That feels more like a research workstation than a simple search box.

## Effect Comparison

> ⚠️ The "3 local comparison samples" below are from a smaller, earlier
> test, not the 2026-07-03 Phase 3 18-task controlled experiment -- see the
> "Owner decision needed" section at the top of this document and
> `experiments/salva_v2/ANALYSIS_FINDINGS.md`.

The comparisons below come from a local demo script that contrasts direct advice and agent-guided advice.

### A. `find_leads`

Direct Salva usage tends to stay in:

- `quick_scan`
- short, narrow next queries

With agent overrides, the advice can move into:

- `company_research`
- broader company-oriented next queries

This shows that Salva can promote a lead task into a deeper research route when the context changes.

### B. `find_companies`

Both direct and agent-guided paths often stay in `company_research`, but the next queries still change with the agent context.

So even when the route is the same:

- the query family can change
- the follow-up path can still improve

### C. `find_market_activity`

Deeper tasks usually move toward:

- `deep_investigation`
- or `platform_integrator`

In these cases, the value is not a single query. The value is:

- seed the signal
- use pilot for the next step
- use audit and mate to judge whether to expand further

### D. Local measurement snapshot

Across 3 local comparison samples:

- `next_queries` changed in `3/3` runs
- route / profile switch happened in `1/3` runs
- deeper tasks naturally landed on `deep_investigation` or `platform_integrator`

The point is not “more queries”. The point is “a better next round”.

## Why It Beats Direct Search

- Direct search returns results; Salva returns routes
- Direct search has no memory; Salva has query-family memory
- Direct search has no audit trail; Salva has audit, telemetry, and evidence
- Direct search has no hypergraph; Salva turns a run into a walkable research structure
- Direct search has no tenant controls; Salva can serve team scenarios
- Direct search has no route catalog; Salva maps intent to explainable flows
- Direct search cannot quality-gate a fan-out expansion; Salva can open more providers when signal is weak

## Best-Fit Scenarios

- lead discovery
- company research
- market activity scanning
- partnership signals
- event discovery
- internal research operations
- agent workflow orchestration
- auditable research pipelines

## Not a Great Fit

- you only need a short real-time answer
- you do not need evidence, telemetry, routing, or memory
- you do not want to manage structured intent

In those cases, a direct search tool is simpler.

## Comparison Matrix

| Type | Strength | Weakness | What Salva adds |
|---|---|---|---|
| Manual Google search | broad web coverage, familiar, free | the human has to plan, dedupe, and remember everything | routes, memory, evidence, audit, tenant boundaries |
| Google Programmable Search / Custom Search API | programmatic retrieval | still single-pass; you must design the research flow | multi-round pipeline, pilot, hold, memory |
| Perplexity-style search API | readable results and summaries | weaker reusable routing and research structure | route catalog, graph walk, query-family memory |
| Tavily-style LLM search API | agent-friendly and cleaned output | still mostly single-search oriented | hypergraph, audit, deep modes, observability |
| Exa-style semantic search API | strong semantic / similarity search | less research workflow and retention | multi-round pipeline, memory, evidence chains |
| Human raw research | maximum flexibility | slow, leaky, hard to reuse | systemized research that compounds over time |

If you only want a single answer, the other tools are enough.
If you want the next answer to get smarter, Salva starts to win.

This comparison is based on public official docs for Exa, Tavily, Perplexity, and Google Programmable Search. For stable behavior, still defer to each product's own docs and this repo's `docs/spec/`.

## Recommended Research Flow

1. Inspect `GET /v1/routes`
2. Run `POST /v1/discover` or `POST /v1/jobs`
3. Use `POST /v1/pilot` for the next round
4. Use `GET /v1/audits/{run_id}` and `POST /v1/mate/{run_id}` to evaluate outcome
5. Let query-family memory accumulate if the same pattern repeats

The goal is not just more results. The goal is better results over time.

## One-line pitch

> Salva turns search into a research system, and turns every run into reusable routing, memory, and hypergraph structure.

Or more bluntly:

> It does not just help you search more. It helps you stop searching blind.

## Entry Points

- `README.md`
- `README.zh.md`
- `docs/README.md`
- `docs/spec/README.md`
