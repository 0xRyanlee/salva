# Salva — Claude Code Skill

Salva is a structured discovery intelligence runtime. Use its MCP tools when the
user asks to research a company, find equity holdings, trace ownership structures,
or discover entities in a domain.

## When to invoke

- User asks to research a company: `salva_discover` or `salva_job_create`
- User asks for ownership / shareholding / 股權 / 持股 structure → `salva_discover` with `objective: find_companies`
- User wants to trace a 一致行動人 group → include `acting_in_concert` in signal_terms
- User wants to check a previous run → `salva_run_result` with run_id
- User wants audit trail → `salva_audit` with run_id

## MCP tools available

| tool | when to use |
|---|---|
| `salva_discover` | Synchronous single-shot discovery (small jobs, ≤3 rounds) |
| `salva_job_create` | Async job for larger runs; use when rounds > 3 |
| `salva_job_status` | Poll job status; call every 5s until status = completed |
| `salva_run_result` | Fetch entities from a completed run |
| `salva_audit` | Fetch evidence chains and telemetry for a run |
| `salva_pilot` | Ask Salva for next-step guidance given prior results |
| `salva_vocab` | Inspect available domain vocabularies |

## Standard discovery workflow

```
1. salva_discover(intent={domain, objective, primary_terms, market, industry})
   → returns entities[], run_id, meta

2. If job is async: salva_job_status(job_id) → poll → salva_run_result(run_id)

3. Review entities. If more depth needed: salva_pilot(run_id) → next suggestions

4. salva_audit(run_id) → evidence chains, source reliability, telemetry
```

## Intent construction guide

```json
{
  "domain": "companies",
  "objective": "find_companies",
  "primary_terms": ["TSMC", "台積電"],
  "market": "Taiwan",
  "industry": "semiconductor",
  "region": "TW",
  "max_rounds": 3,
  "results_per_round": 10,
  "domain_hints": {
    "signal_terms": ["acting in concert", "一致行動人", "SC 13D"],
    "source_hints": ["sec.gov", "twse.com.tw", "mops.twse.com.tw"]
  }
}
```

## Domain options

| domain | use case |
|---|---|
| `companies` | Company research, equity, ownership |
| `market_intel` | Market activity, sector intelligence |
| `partnerships` | Partnership signals, alliances |
| `events` | Event discovery |
| `bd_leads` | BD lead generation |
| `general` | Unknown / catch-all |

## Output interpretation

- `entities[]` — scored entities. Check `relevance_score` (0–1) and `qualified: true`.
- `run_id` — use for audit, result fetch, and pilot requests.
- `meta.memory_seeds_used` — how many content terms were injected from prior runs (compounding signal).
- `meta.retrieval_health` — `"ok"` / `"degraded"` / `"probe_failed"`; treat `"probe_failed"` results as unconfirmed, not just low-confidence.
- Evidence chains in `salva_audit` show the source, jurisdiction, and legal availability.

## Optional: stability gating

`salva_discover(..., enable_stability_gating=True)` opts into an experimental scoring
adjustment based on how stable this domain's historical query-family memory has been
(drift + volatility). **Disabled by default**, and needs prior history for the domain
to have any effect at all — safe to leave off for first-time or unfamiliar domains.

## Beachhead: listed company equity intelligence

For listed company ownership research, prefer:
- `objective: find_companies`
- `domain_hints.source_hints: ["sec.gov", "twse.com.tw", "mops.twse.com.tw", "hkexnews.hk"]`
- `domain_hints.signal_terms: ["acting in concert", "一致行動人", "beneficial owner", "SC 13D"]`

SEC EDGAR is the most reliable source (free JSON API, no CAPTCHA). MOPS (Taiwan) is reliable for
listed companies. CN gsxt is unreliable (anti-scraping) — Salva routes around it automatically.
