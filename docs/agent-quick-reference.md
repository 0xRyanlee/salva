# Salva — Agent Quick Reference

One-page index for agents and callers. Read this before calling any Salva tool.

---

## What Salva Does

Structured discovery pipeline: intent in → multi-round retrieval + graph expansion → scored entities + evidence out.

Single-call value ≈ direct search. Compound value emerges after several runs seed `query_family_memory`.
See [value-model.md](value-model.md) for the full model.
See [spec/README.md](spec/README.md) for the canonical contracts.

---

## Tools at a Glance

| Tool / Endpoint | When to call | Sync? |
|----------------|-------------|-------|
| `salva_discover` / `POST /v1/discover` | Quick lookup, ≤ 20 results, can wait | ✅ |
| `salva_job_create` / `POST /v1/jobs` | Large jobs, background, poll for result | async |
| `salva_job_status` / `GET /v1/jobs/{id}` | Poll async job | ✅ |
| `salva_run_result` / `GET /v1/runs/{id}` | Retrieve completed run entities | ✅ |
| `salva_audit` / `GET /v1/audits/{id}` | Inspect evidence chains + source attempts | ✅ |
| `salva_pilot` / `POST /v1/pilot` | Get next-step query suggestions after a run | ✅ |
| `scripts/compare_agent_mode.py` | Compare direct advice vs agent-guided advice | ✅ |
| `salva_mate` / `POST /v1/mate/{id}` | Estimate time/token/cost savings vs manual | ✅ |
| `GET /v1/routes` | Inspect the discovery route index before choosing a pipeline | ✅ |

---

## Objectives → Profiles → Strategy Rotation

Salva maps your `objective` to an experience profile, which determines which retrieval
strategies run and in what order. You don't choose the strategy — you declare the intent.

If you need a fast decision surface, call `/v1/routes` first. It returns the canonical
profile, strategy rotation, and recommended call surfaces in one place.
The formal route contract is in [spec/route-catalog.md](spec/route-catalog.md).

| objective | profile | strategy rotation | rounds |
|-----------|---------|-------------------|--------|
| `find_leads` | `lead_focus` | dive → anchor | 2 |
| `find_companies` | `company_research` | dive → anchor → radar | 3 |
| `find_events` / `find_exhibitors` | `event_discovery` | radar → anchor | 2 |
| `find_market_activity` | `deep_investigation` | anchor → radar → pirate | 3 |
| `find_partnership_signals` | `deep_investigation` | anchor → radar → pirate | 3 |
| *(short query, no role/product)* | `quick_scan` | dive | 1 |
| *(role or product specified)* | `lead_focus` | dive → anchor | 2 |
| *(output_profile = company_profile / crm_contact)* | `platform_integrator` | dive → anchor | 2 |

### Strategy meanings

| Strategy | Character | Query style |
|----------|-----------|-------------|
| **dive** | Precision-first | Exact phrases + negative terms. Seeds the run. |
| **anchor** | Recall/expansion | Role + primary + signal combos. Expands the graph. |
| **radar** | Broad discovery | Signal sweeps + source-hint site: queries. Finds unknowns. |
| **pirate** | Operator-heavy | filetype: intitle: inurl: site: — document probing, noise-tolerant. |

---

## Retrieval Modes

Set on the request via `retrieval.mode`:

| mode | Behaviour |
|------|-----------|
| `auto` (default) | SearXNG local → Whoogle → DDG HTML fallback |
| `local_first` | Prefer self-hosted instances; fail hard if none |
| `wall_guarded` | Public fallbacks disabled; only local providers |

---

## salva-search Skill (retrieval sub-tool)

The `salva-search` skill provides provider-level retrieval:
- SearXNG (local) → Whoogle → DDGS → Exa (if `EXA_API_KEY` set)
- HackerNews Algolia (for `find_companies`, `find_leads`, `find_market_activity`)
- OpenAlex / arXiv (for `find_research`, `find_academic`)
The formal retrieval/provider contracts are in [spec/retrieval-contract.md](spec/retrieval-contract.md) and [spec/provider-contract.md](spec/provider-contract.md).

**Use directly when**: you need raw search results outside the full pipeline.
**Use via Salva pipeline when**: you want multi-round expansion, graph seeding, entity
extraction, scoring, evidence chains, and memory accumulation.

The skill is a retrieval building block; the pipeline is where intelligence compounds.

---

## Delivery Profiles

Set `output_profile` to shape what entities look like in the response:

| output_profile | Fields included |
|---------------|----------------|
| `company_profile` | name, domain, description, funding, team, signals |
| `lead` | name, role, company, contact hints, signals |
| `crm_contact` | name, email hints, linkedin, company |
| `event` | name, date, venue, organizer, url |
| `activity_signal` | entity, signal type, date, source, confidence |
| *(omit)* | Raw `UnifiedResult` — all fields |

---

## mate + pilot: Post-Run Intelligence

After a run completes, two tools help you decide what to do next:

**pilot** — suggests refined queries and next objectives based on what was found:
```
POST /v1/pilot
{ "run_id": "...", "market": "US", "industry": "fintech", "objective": "find_companies" }
```

**mate** — estimates how much time, tokens, and cost Salva saved vs. doing it manually:
```
POST /v1/mate/{run_id}
{ "pricing": { "usd_per_1k_tokens": 0.015 } }
```

Both are available as `salva_pilot` / `salva_mate` in the MCP server and via CLI.

---

## Minimal Call Example (REST)

```json
POST /v1/discover
{
  "objective": "find_companies",
  "intent": {
    "market": "US",
    "industry": "legal tech"
  },
  "max_results": 20,
  "output_profile": "company_profile"
}
```

Returns: `{ "entities": [...], "run_id": "...", "meta": { "experience_profile": "company_research", ... } }`

Use `run_id` immediately with `salva_pilot` for next-step suggestions.

---

## When Salva Beats Direct Search

- **Always**: structured output, evidence chains, source telemetry, dedup across rounds
- **After 3+ runs on same objective/market**: graph seeding from `query_family_memory`
  makes queries progressively more targeted
- **Multi-round objectives** (`find_market_activity`, `find_partnership_signals`):
  pirate round surfaces documents and sources that keyword-only search misses
- **Never**: when you need a single answer fast and don't care about structure
