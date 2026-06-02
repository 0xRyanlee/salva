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
  → extract → normalize → dedupe → classify → score (all deterministic)
  → enrichment (LLM via omlx — scoped, bounded prompts only)
```

Do not expand the LLM's role inside the core pipeline without discussion.

## Architecture Boundaries

| Layer | Files | Rule |
|-------|-------|------|
| API Gateway | `apps/api/main.py` | Only routing, validation, response shaping. No business logic. |
| Orchestration | `core/controller.py` | Multi-round strategy only. No retrieval details. |
| Query Intelligence | `core/keyword_graph.py`, `core/domain_vocab.py` | Expansion and feedback. Vocab is injectable via DomainVocab registry. No scoring. |
| Retrieval | `retrieval/` | Provider adapters only. Each source is isolated. |
| Processing | `processing/` | Pure functions. No I/O. |
| Enrichment | `enrichment/` | Bounded prompts only. No free-form LLM calls. |
| Persistence | `salva_core/persistence.py` | SQLite store. Will be split — see TODO Phase R1. |
| Schema | `salva_core/schemas.py` | Canonical types. `schema/` is a legacy bridge to be removed. |

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

## GUI Fork

A GUI product (working name: `salva-ui`) is explicitly out of scope for this repository.

When ready, it should be:
- A separate GitHub repository
- Built against the stable REST API + MCP server contracts
- Released independently (not as a branch of this repo)
- Potentially Electron, Tauri, or a Next.js app

**Do not add any frontend code to this repository.**

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
