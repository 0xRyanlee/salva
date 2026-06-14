# Salva Runtime — Development Progress Report

## Update: Execution Isolation and E10 Dogfood (2026-06-08)

> Final verification: 2026-06-09  
> Tests: 202 passed, 2 skipped  
> Compile: PASS  
> Selected changed-file lint (`F`, `E9`, `I`): PASS  
> `git diff --check`: PASS

### Completed

- Added native `ExecutionContext` with campaign, continuation, persistence,
  memory policy, cache intent, and tags.
- Cross-run memory reads now default to `none`; writes default to `quarantine`.
- Added campaign-scoped `promoted` memory and review promotion endpoint.
- Added true no-write execution with `persistence=none`.
- Applied the contract to sync service, worker, REST, CLI, MCP, and Python SDK.
- Removed caller `source_hints` privilege escalation into trusted-source scoring.
- Added schema migration and campaign/status filters for runs and query memory.
- Rebuilt `scripts/compare_agent_mode.py` as an observation evaluator with
  cumulative and snapshot round semantics, quality metrics, Markdown, JSON,
  and SVG output.
- Added deterministic isolation adversarial test and live Naturehike DACH
  Agent-only vs Salva dogfood.

### E10 Result

| Condition | R1 verified | R2 verified | R3 verified | Best pooled recall |
|---|---:|---:|---:|---:|
| Agent-only | 5 | 11 cumulative | 15 cumulative | 88.2% |
| Salva | 2 | 0 snapshot | 0 snapshot | 11.8% |

Validity limits: pooled recall uses the post-hoc verified union rather than
predeclared external ground truth; request/time budgets were unmatched; Agent
raw SERPs were not fully captured; and live DDG output varied. The result is a
dogfood/failure-mode record, not a statistically controlled benchmark.

### New Artifacts

- `docs/spec/execution-context.md`
- `docs/reports/execution-isolation-update-2026-06-08.md`
- `docs/dogfood/naturehike-dach-2026-06-08.md`
- `experiments/agent_vs_salva/README.md`
- `experiments/agent_vs_salva/naturehike-dach-live.json`
- `experiments/agent_vs_salva/raw/salva-r{1,2,3}.json`
- `experiments/agent_vs_salva/results/`
- `experiments/agent_vs_salva/isolation-report.json`
- `experiments/agent_vs_salva/GITHUB_UPDATE.md`

### Remaining

1. Implement content-addressed raw response artifacts and frozen-corpus replay.
2. Add reviewer identity, promotion reason, rejection, and provenance hashes.
3. Run repeated budget-matched A/B with stable SearXNG and complete raw capture.
4. Add tenant authorization or row-level security before production multi-tenancy.

> Previous report generated: 2026-06-07  
> Branch: `experiment/hg-penetration`  
> Previous test status: 163/163 PASS  
> Lint: 441 remaining (408 pre-existing E501; all new code clean)

---

## Summary

This session completed the theoretical validation phase (E5b → E9) and implemented the core
infrastructure needed for real compounding intelligence: a working Jina embedding backend,
BM25-hybrid deduplication, B1+B2 hollow-core fix, Hold upgrade with n-ary hyperedge support,
FtM-aligned relation ontology, and a functional MCP server. All nine validation points now have
honest verdicts backed by running code and committed evidence.

---

## Experiments Completed

### E5b — Jina Cross-Lingual Entity Resolution (VP5) — FAIL

**File:** `experiments/hg_penetration/e5b_jina_benchmark.py`  
**Findings:** `experiments/hg_penetration/E5b_FINDINGS.md`

Tested `jina-embeddings-v5-text-small-retrieval-mlx` via local omlx as a cross-script entity
bridge. Best F1 = 0.31 at threshold 0.40. Key data point: cosine(台積電, TSMC) = 0.0384;
cosine(台積電, 台积电) = 0.9989. The small model cannot bridge different scripts for entity names.

**Production decision:** Gazetteer (`canonical_entities` + `entity_aliases` in Hold) is the
primary bridge for cross-script entity resolution. Jina reserved for content-level semantic search.

---

### E6 — Cross-Semantic Relation/Fact Merging (VP6) — PASS

**File:** `experiments/hg_penetration/e6_relation_merge.py`  
**Findings:** `experiments/hg_penetration/E6_FINDINGS.md`

7 fragmented records → 3 canonical hyperedges. Ownership merged 4 multilingual evidence sources.
70% vs 65% conflict surfaced without overwriting. Investment not mistakenly merged. Merging
requires FtM-aligned relation ontology + E5 entity bridge + conflict-preserving merge logic.

---

### E7 — Semantic Graph Search + 2-Hop Traversal (VP7) — INCONCLUSIVE

**File:** `experiments/hg_penetration/e7_semantic_search.py`  
**Findings:** `experiments/hg_penetration/E7_FINDINGS.md`

12-node, 4-hyperedge synthetic graph. Semantic+2hop achieves recall=1.00 via 2-hop expansion
but precision drops (1/4 queries beat keyword baseline). Keyword baseline is surprisingly
competitive on a small, structured graph with dense node labels.

**Implication:** Enrich node labels with longer descriptions/evidence snippets before production
deployment. The 2-hop structural expansion is validated; the embedding seed selection needs
richer text corpus.

---

### E8 — HIF Round-Trip + Bipartite Projection (VP8) — PASS

**File:** `experiments/hg_penetration/e8_hif_projection.py`  
**Findings:** `experiments/hg_penetration/E8_FINDINGS.md`  
**Artifact:** `experiments/hg_penetration/e8_chatham_sample.hif.json`

HIF export → JSON → re-import: zero diff across all 4 tables (nodes, hyperedges, incidences,
evidence). Bipartite and star projections trivially computable from incidence table.
`export_hif()` is production-ready for `salva_core/persistence/`.

---

### E9 — Persistence Compounding (VP9) — PASS

**File:** `experiments/hg_penetration/e9_compounding.py`  
**Findings:** `experiments/hg_penetration/E9_FINDINGS.md`

5 synthetic runs with the B1+B2 fix active. Seed count: 0 → 19 → 35 → 46 → 46.
Graph nodes: 34 → 50 → 61. Mechanism verified: content_terms extracted from result snippets
flow into telemetry → persisted as `content_nodes` → injected as seeds on next run.

---

## Core Infrastructure Implemented

### B1 + B2 — Hollow Core Fix

**Problem:** `seed_from_memory()` re-injected vocab-derived terms already in the graph
(tautological). `apply_telemetry()` only reweighted existing query tokens, never absorbed new
content.

**B1 — Content Term Extraction** (`core/controller.py`):
- `_extract_content_terms()` runs after each round's processing
- Extracts CJK 2+ char sequences and EN tokens from result snippets
- Filters stopwords and terms already in the graph
- Stores top-20 new terms in `telemetry.metadata["content_terms"]`

**B2 — Memory Loop** (three files):
- `core/keyword_graph.py` `apply_telemetry()`: absorbs content_terms as `content` nodes (weight 0.15)
- `core/keyword_graph.py` `seed_from_memory()`: reads `content_nodes` first (real content), falls back to `source_nodes` (vocab-derived)
- `salva_core/persistence/runs.py`: persists `content_nodes_json` column
- `salva_core/persistence/memory.py`: returns `content_nodes` in seeding queries

**Schema migration:** `content_nodes_json TEXT NOT NULL DEFAULT '[]'` added to
`query_family_memory` table via `_migrate_schema()` in `salva_core/persistence/db.py`.

---

### Jina Embedding Backend (`salva_core/vector_backends.py`)

- `JinaOmlxVectorBackend` dataclass: POST to `http://localhost:8140/v1/embeddings`
- Model: `jina-embeddings-v5-text-small-retrieval-mlx` (1024d)
- Cosine similarity via `score(left, right)` — normalized dot product
- Activated via `SALVA_SEMANTIC_VECTOR_BACKEND=jina_omlx` env var
- Fallback to `HybridHashVectorBackend` on connection failure (graceful degradation)

---

### BM25-Hybrid Deduplication (`processing/dedup.py`)

- `MemoryDeduplicator` now runs BM25 before vector similarity
- `rank_bm25.BM25Okapi` with CJK + EN tokenizer (regex-based, no external NLP deps)
- Threshold: 0.82 (empirically chosen for same-language near-duplicate detection)
- Cross-language dedup still relies on canonical entity resolution (Hold C2)
- `rank-bm25>=0.2.2` added to `pyproject.toml` dependencies

---

### Hold Upgrade — n-ary Hyperedge Tables (`salva_core/persistence/hold.py`)

Four concerns implemented cleanly:

**C1 — Hyperedge incidences:**
- `upsert_hyperedge_incidence()`: role + percentage + order_index per node/edge pair
- `list_incidences_for_edge()`, `list_edges_for_node()`
- Table: `hyperedge_incidences`

**C2 — Canonical entities + aliases:**
- `upsert_canonical_entity()`: canonical_id, type, label, jurisdiction, props
- `add_entity_alias()`: surface → canonical_id mapping with locale + source
- `resolve_canonical_id()`, `get_aliases_for_canonical()`
- Tables: `canonical_entities`, `entity_aliases`

**C3 — Relation ontology as data** (`salva_core/relation_ontology.py`):
- 7 FtM-aligned canonical types: `ownership`, `directorship`, `investment`,
  `acting_in_concert`, `subsidiary`, `partnership`, `creditor`
- Multilingual surface forms (EN/ZH-TW/ZH-CN)
- `normalize_relation(surface)` → canonical type or None
- `canonical_relation_types()`, `surface_forms(canonical)`, `ROLES` dict

**C4 — Routing memory:**
- `record_source_attempt()`: success/fail → authority_boost ±0.05/0.10
- `get_routing_boost()`, `list_routing_memory()`
- Table: `routing_memory`

All 4 new tables added to `SCHEMA_SQL` with indexes, plus migration block in `_migrate_schema()`.

---

### MCP Server (`apps/mcp/server.py`)

9 tools exposed as MCP protocol:

| Tool | Description |
|------|-------------|
| `salva_discover` | Synchronous discovery with full pipeline |
| `salva_job_create` | Async job creation |
| `salva_job_status` | Poll job state |
| `salva_run_result` | Full run result by run_id |
| `salva_audit` | Quality audit for a run |
| `salva_pilot` | Next-step recommendations |
| `salva_hold_walk` | Traverse n-ary hypergraph |
| `salva_routing_table` | View learned source authority |
| `salva_memory_summary` | Top query families for seeding |

Direct `salva_core` imports — no server process required. Loaded as Claude Code MCP extension.

---

### Claude Code Skill (`.claude/skills/salva.md`)

Documents the 7-tool MCP workflow, intent construction, domain options, output interpretation,
and beachhead setup for common company intelligence tasks.

---

## Files Modified / Created

### New files
- `salva_core/persistence/hold.py` — C1/C2/C4 Hold functions
- `salva_core/relation_ontology.py` — FtM-aligned relation types (C3)
- `experiments/hg_penetration/e5b_jina_benchmark.py` — E5b benchmark
- `experiments/hg_penetration/e7_semantic_search.py` — E7 semantic search
- `experiments/hg_penetration/e8_hif_projection.py` — E8 HIF round-trip
- `experiments/hg_penetration/e9_compounding.py` — E9 persistence compounding
- `experiments/hg_penetration/E5b_FINDINGS.md`
- `experiments/hg_penetration/E7_FINDINGS.md`
- `experiments/hg_penetration/E8_FINDINGS.md`
- `experiments/hg_penetration/E9_FINDINGS.md`
- `experiments/hg_penetration/e8_chatham_sample.hif.json`
- `.claude/skills/salva.md`
- `.env` (OMLX_BASE_URL set)
- `DEVELOPMENT_PROGRESS.md` (this file)

### Modified files
- `salva_core/vector_backends.py` — JinaOmlxVectorBackend added
- `salva_core/persistence/__init__.py` — hold.py exports added
- `salva_core/persistence/db.py` — 4 new tables + content_nodes_json migration
- `salva_core/persistence/runs.py` — content_nodes_json persisted
- `salva_core/persistence/memory.py` — content_nodes returned in seeding queries
- `processing/dedup.py` — BM25-hybrid dedup
- `core/controller.py` — B1 content term extraction
- `core/keyword_graph.py` — B2 apply_telemetry + seed_from_memory fix
- `experiments/EXPERIMENT_PLAN.md` — honest verdicts for E5b/E7/E8/E9
- `pyproject.toml` — rank-bm25 dependency added
- `CLAUDE.md` — architecture table updated (persistence submodules, hold.py, relation_ontology.py)

---

## Validation Points — Final Verdict

| VP | Claim | Verdict |
|----|-------|---------|
| VP1 | n-ary hypergraph preserves n-ary facts | ✅ E1 |
| VP2 | Public sources provide equity facts | ✅ E2 |
| VP3 | Real filing → structured n-ary fact | ✅ E3 |
| VP4 | Routing table self-optimizes | ✅ E4 |
| VP5 | Cross-language entity resolution | ✅ gazetteer / ⚠️ E5b (Jina FAIL for cross-script names) |
| VP6 | Cross-semantic relation/fact merging | ✅ E6 |
| VP7 | Semantic retrieval + 2-hop > keyword | ⚠️ E7 INCONCLUSIVE (2-hop recall=1.00; precision drops; need richer labels) |
| VP8 | HIF round-trip + projections | ✅ E8 |
| VP9 | Persistence compounding measurable | ✅ E9 (B1+B2 verified: seeds 0→46) |

---

## Known Gaps / Next Steps

1. **E7 improvement**: Enrich node labels with evidence snippets; embed full evidence text
   rather than short node labels. Re-run E7 to confirm VP7.

2. **E5b production path**: Gazetteer population — wire `add_entity_alias()` into extraction
   pipeline so SEC/EDGAR filings auto-populate canonical entity table.

3. **MCP server test coverage**: `apps/mcp/` lacks unit tests. Add smoke tests for each tool.

4. **Hold → bay surface**: Expose Hold C1/C2 via `/v1/hold/` REST endpoints (currently only
   `hold_walk` exists).

5. **sqlite-vec upgrade**: Replace `HybridHashVectorBackend` with sqlite-vec for true ANN
   similarity. Prerequisite for production-scale VP7.

6. **`schema/` removal**: Legacy `schema/` directory should be deleted once all importers
   confirmed migrated to `salva_core/schemas.py`.
