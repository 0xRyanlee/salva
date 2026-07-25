# Salva Runtime — Project Context for Claude Code

## What This Project Is

Salva Runtime is a **self-hosted Discovery Intelligence Runtime** — a structured retrieval and entity extraction service designed to be called by AI agents, CLI tools, and LLMs via stable APIs or MCP.

It is not a scraper. It is not a UI product. It is a composable intelligence pipeline that accepts structured intent and returns scored entities, evidence chains, relations, and telemetry.

## Core Product Philosophy

### Event-Triggered, Not Schedule-Driven

Salva's core business logic is **event-triggered close-loop execution**:

```
trigger (agent / CLI / API call)
  → structured intent in
  → multi-round retrieval + processing
  → scored entities + evidence out
  → caller acts on result
```

This is a deliberate choice. Salva does NOT own scheduling, polling, or monitoring loops. Those concerns belong to the caller (agent, CLI, or orchestrator). Salva responds to calls — it does not initiate them.

If a caller wants recurring execution, they call Salva on a cron from their own scheduler. Salva stays stateless between calls.

### API-First, Agent-Native

The primary integration surface is:

1. **REST API** (`/v1/discover`, `/v1/jobs`, `/v1/runs`) — direct HTTP from any caller
2. **MCP Server** — for Claude Code, Claude Desktop, and any MCP-compatible agent
3. **CLI skill wrapper** — for terminal-native agent workflows and Codex integration
4. **Python SDK** — thin wrapper for Python-based agent code

There is no GUI in this repository. A GUI product may be developed as a **separate fork** — see "GUI Fork" section below.

### Deterministic Pipeline First

LLMs are bounded reasoning modules, not the pipeline itself. The enrichment order is:

```
keyword expansion (deterministic)
  → retrieval (multi-provider, policy-aware)
    → optional bounded LLM query-proposal step (scoped prompt, proposes
      follow-up queries only — not free-form reasoning; amended 2026-07-21,
      see below)
  → extract → normalize → dedupe → classify → score (all deterministic)
  → enrichment (LLM via omlx — scoped, bounded prompts only)
```

**Amendment 2026-07-21**: the retrieval loop may include a bounded LLM
query-proposal step (scoped prompt requesting follow-up search queries
only, not free-form reasoning). Owner-approved after a fable-led review
found pure deterministic query expansion under-fetches primary sources
that a freely-searching agent can find (CNCF founders case: Salva's
multi-round retrieval fetched a Wikipedia secondary list, missed the
original 2015 press release a bare agent found by searching further).
Implementation is gated on the frozen-corpus replay harness
(`salva-methodology-frozen-corpus-harness` on the board) so the change
can be evaluated reproducibly offline before going live — do not wire
this into `core/controller.py` before that harness exists.

Do not expand the LLM's role beyond this scoped query-proposal step
without further discussion.

## Architecture Boundaries

| Layer | Files | Rule |
|-------|-------|------|
| API Gateway | `apps/api/main.py` | Only routing, validation, response shaping. No business logic. |
| Orchestration | `core/controller.py` | Multi-round strategy only. No retrieval details. |
| Query Intelligence | `core/keyword_graph.py`, `core/domain_vocab.py` | Expansion and feedback. Vocab is injectable via DomainVocab registry. No scoring. |
| Retrieval | `retrieval/` | Provider adapters only. Each source is isolated. |
| Processing | `processing/` | Pure functions. No I/O. |
| Enrichment | `enrichment/` | Bounded prompts only. No free-form LLM calls. |
| Persistence | `salva_core/persistence/` | SQLite store — split into `db.py`, `runs.py`, `memory.py`, `hold.py`, `jobs.py`, `evidence.py`, `telemetry.py`, `usage.py`. |
| Hold (n-ary) | `salva_core/persistence/hold.py` | Hyperedge incidences, canonical entities + aliases, routing memory. Do not add business logic here. |
| Relation Ontology | `salva_core/relation_ontology.py` | FtM-aligned relation types as data. Extend the `_RELATION_MAP` dict; never hardcode relation strings elsewhere. |
| Schema | `salva_core/schemas.py` | Canonical types. `schema/` directory removed. |

## Key Design Decisions (Do Not Reverse Without Discussion)

**Salva is domain-agnostic.** The service must work for any discovery direction — events, BD leads, company research, market intelligence, legal, academic, or anything a caller passes in. Do not treat `events` and `bd_leads` as the only valid states. Any hardcoded domain assumption is a bug.

**DomainVocab is injectable, not hardcoded.** `core/domain_vocab.py` owns a registry with built-in reference implementations (`events`, `bd_leads`, `companies`, `market_intel`, `partnerships`, `general`). Callers can override via `DiscoveryRequest.intent.domain_hints`. Unknown domains fall back to `general`, never to `bd_leads`. Do not add new hardcoded domain branches to `keyword_graph.py` or `query_strategy.py` — extend the registry instead.

**Objective-to-domain mapping must be accurate.** `find_companies` → `companies`, `find_market_activity` → `market_intel`, `find_partnership_signals` → `partnerships`. Never let non-events objectives silently inherit `bd_leads` vocabulary.

**Semantic memory must be connected to bootstrap.** `query_family_memory` is not just a query log — it is a learning substrate. `KeywordGraph.seed_from_memory()` must be called before each run to inject high-scoring past nodes. A runtime that doesn't use its own memory is not learning.

**ScorerConfig is injectable.** `NOISE_DOMAINS` and `TRUSTED_SOURCES` are defaults in `processing/scorer.py`, not global constants. Every caller controls their own trust lists via `ScorerConfig`. Do not add hardcoded domain lists back.

**Output profiles are caller-specific transforms.** The canonical entity schema does not change. Only `salva_core/transforms.py` shapes output per caller. Never add caller-specific fields to the canonical schema.

**Hold is the hypergraph container; bay is its surface.** Entity/relation/evidence/hyperedge persistence lives in Hold. The bay exposes the contract surface. Do not mix them.

**Job IDs are the unit of observability.** Every discovery run gets a `run_id` and a `job_id`. Evidence chains, telemetry, source attempts, and plugin reports all trace back to `run_id`. Never bypass persistence for a "quick" response.

## MCP Integration (Target Architecture)

Salva should expose these as MCP tools:

```
salva_discover       — POST /v1/discover (synchronous, small jobs)
salva_job_create     — POST /v1/jobs (async, large jobs)
salva_job_status     — GET /v1/jobs/{job_id}
salva_run_result     — GET /v1/runs/{run_id}
salva_audit          — GET /v1/audits/{run_id}
salva_pilot          — POST /v1/pilot (next-step guidance)
```

The MCP server lives at `apps/mcp/` (to be created). It wraps the same FastAPI service — no business logic duplication.

## CLI Skill Wrapper (Target Architecture)

```bash
# Direct invocation
salva find --market Germany --industry software --role reseller

# As a skill from agent CLI
/salva find ...

# Pipeline output (JSON stdout for agent consumption)
salva find --market Germany --industry software | jq '.entities[]'
```

The CLI lives at `apps/cli/` (to be created). It consumes the REST API — no direct Python imports from core.

## GUI / Interface（2026-07-25 owner 拍板，推翻先前「不加前端」規則）

**先前規則已由 owner 明確推翻**：salva 定位比照 Mindset——要能被生態內其他 app 呼叫（MCP/REST），**也要能被直接使用**（獨立介面），不能只靠 Mindset/EditorsNote 投影它的視覺呈現。owner 原話：「salva 有自己的界面和 mcp，方便獨立進行檢索任務和可視化，同時也可以深度了解 nodes 之間的 hyper edges 的動態流形關係，也需要可視化的文檔查閱 diff（可以借鑑 paperclip）」。

**需要的能力**（新方向，取代舊的「out of scope」）：
- Hyperedge / node 動態流形關係視覺化（HIF 超圖的互動式呈現，不只是靜態匯出）
- 文檔查閱 + diff 檢視（借鑑 Paperclip 的審閱 UI 模式）
- 獨立檢索任務操作介面（不透過其他 app 中介）

`apps/desktop/`（或等效目錄）目前是否已有實作進度、要留在本 repo 還是拆成獨立的 `salva-ui` repo（原規則傾向獨立 repo + 消費穩定 REST/MCP 契約，這個結構性原則本身仍合理，只是「要不要做」這個大前提已經反轉），交給實際承接這個方向的 CC 先盤點現況再定案，不預設答案。

~~舊規則（已廢止，保留供對照）~~：~~A GUI product is explicitly out of scope. Do not add any frontend code to this repository.~~

## Code Quality Standards

- **Python 3.11+**, strict mypy, ruff lint
- No module should exceed ~400 lines without a clear reason. `persistence.py` (1854 lines) is flagged for split — see TODO.
- Tests use neutral, generic fixtures — not industry-specific example data
- No hardcoded domain lists, credentials, or business-specific signals in core modules
- All LLM prompts in `enrichment/` — none in `processing/`, `core/`, or `apps/`

## Running Locally

```bash
# Install Python dependencies
pip install -e ".[dev]"

# Install Obscura headless browser (required for radar/pirate content fetch)
./scripts/install_obscura.sh

# Start service
python3 -m uvicorn apps.api.main:app --reload --port 8000

# Run tests
pytest

# Lint + typecheck
ruff check . && mypy .
```

## Environment Variables

```bash
# Search providers
SEARXNG_URL=http://localhost:8080        # optional — skip with SEARXNG_ENABLED=false
SEARXNG_ENABLED=true                     # set false to skip SearXNG entirely (no Docker needed)
SEARXNG_FALLBACK_URLS=https://searx.be
WHOOGLE_URL=https://whoogle.example.org  # optional

# Obscura headless browser (auto-detected from PATH after install_obscura.sh)
OBSCURA_BIN=obscura                      # custom path if not in PATH
OBSCURA_STEALTH=false                    # true enables anti-fingerprinting (requires stealth build)
OBSCURA_PROXY=                           # socks5://127.0.0.1:1080 or http://...

# Enrichment
OMLX_BASE_URL=http://localhost:8140
OMLX_AUTH_TOKEN=...
OMLX_MODEL=gemma-4-e2b-it-4bit

# Persistence
SALVA_SQLITE_PATH=./data/salva_runtime.db
```
