# Salva Value Model: Retrieval vs. Compound Intelligence

## The Two Phases

Salva's value is not uniform across runs. It grows with use.

### Phase 1 — Pre-seed (first N runs)

In the early phase, Salva behaves as an advanced search orchestrator:

```
intent in → keyword expansion (static vocab) → multi-provider retrieval
          → extract → normalize → dedupe → score → entities out
```

At this stage, a single Salva call is comparable to calling a search API directly.
The added value is structural: provider fallback, output normalization, evidence chains,
and a consistent schema. Not yet a qualitative intelligence advantage.

### Phase 2 — Post-seed (after memory accumulates)

After several runs, `query_family_memory` accumulates high-scoring keyword nodes,
their co-occurrence patterns, and source performance signals.

Each new run calls `KeywordGraph.seed_from_memory()` before expansion:

```
seed_from_memory()        ← inject high-scoring nodes from past runs
     ↓
intent in → keyword expansion (seeded graph) → targeted retrieval
          → extract → normalize → dedupe → score → entities out
          → update query_family_memory        ← compound the learning
```

The graph now knows:
- which terms co-occur with high-scoring entities in this domain
- which sources reliably produce signal for this objective
- which query shapes produce diverse vs. redundant results

Each run is smarter than the last. This is where Salva becomes qualitatively
different from a direct search call.

---

## Why This Matters for Skill Design

A single-call use of the `salva-search` skill or `/v1/discover` API has limited
differentiated value vs. calling DDGS or SearXNG directly.

**The skill and API are the retrieval surface. The pipeline is the intelligence layer.**

Design implication: callers should expect to run Salva multiple times on a domain
before the compound value emerges. The first few runs are seeding, not harvesting.

For route selection, prefer `/v1/routes` or `/v1/experience-plan` instead of
hard-coding strategy choices in agents. The route index exists so callers can
choose the right pipeline without re-encoding policy in every integration.
The canonical route contract is in [spec/route-catalog.md](spec/route-catalog.md).

Recommended usage pattern:
1. Run 3–5 discovery passes on the same objective/market combination.
2. Let `query_family_memory` populate.
3. Subsequent runs will use seeded graph expansion — qualitatively better coverage.

---

## Signals That Drive Compounding

| Signal | Where stored | How used in next run |
|--------|-------------|---------------------|
| High-scoring keyword nodes | `query_family_memory` | Injected into KeywordGraph via `seed_from_memory()` |
| Source performance | `source_attempts` | Provider routing weights future retrieval |
| Entity co-occurrence | `keyword_edges` | Graph expansion paths |
| Query shape → result quality | `search_telemetry` | Strategy selection |
| Evidence chains | `evidence_chains` | Cross-run dedup and confidence boosting |

---

## Development Goal

Every component that touches retrieval or processing must be designed with the
compound model in mind:

- **Retrieval providers** feed the graph — output quality matters more than speed.
- **Keyword expansion** must read from memory before generating queries.
- **Scoring** must write back to memory — not just return a response.
- **CLI and MCP tools** must surface run IDs so callers can track the learning arc.
- **Specs** must stay ahead of implementation changes: use `docs/spec/` as the contract layer.

A Salva deployment that doesn't use its own memory is not learning.
The seeding loop (`seed_from_memory → retrieve → score → write back`) is the
core product differentiator, not the search wrapper.
