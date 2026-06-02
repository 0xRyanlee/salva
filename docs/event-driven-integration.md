# Event-Driven Integration Guide

Salva is an **event-triggered** discovery intelligence runtime.
It responds to calls — it does not schedule, poll, or maintain background loops.

---

## Core Model

```
trigger (agent / CLI / API call)
  → structured intent in
  → multi-round retrieval + processing
  → scored entities + evidence out
  → caller acts on result
```

Salva owns the pipeline. The **caller** owns scheduling.

If you want recurring execution, call Salva from your own cron or event bus.
Salva stays stateless between calls.

---

## Integration Surfaces

### 1. MCP (recommended for Claude Code / Claude Desktop / agents)

```json
// claude_desktop_config.json
{
  "mcpServers": {
    "salva": {
      "command": "python3",
      "args": ["-m", "apps.mcp"],
      "cwd": "/path/to/salva"
    }
  }
}
```

Available tools once connected:

| Tool | When to use |
|------|-------------|
| `salva_discover` | Quick sync search, ≤20 results, return immediately |
| `salva_job_create` | Large async search, fire and check later |
| `salva_job_status` | Poll job progress |
| `salva_run_result` | Fetch full entity + evidence result |
| `salva_audit` | Quality analysis on a completed run |
| `salva_pilot` | Next-step search recommendations |

Example (in Claude Code conversation):

```
Find software resellers in Germany that handle CRM products.
Use salva_discover with market=Germany, industry=software, role=reseller,
output_profile=lead, and inject signal_terms=["CRM", "Salesforce partner"].
```

### 2. CLI (terminal agents, Codex, shell scripts)

```bash
# Install
pip install -e ".[cli]"

# Quick search, JSON output for pipeline
salva find \
  --market Germany \
  --industry software \
  --role reseller \
  --max-results 20 \
  --json | jq '.entities[] | {title, confidence}'

# Async job (fire and check)
salva job create \
  --market US \
  --industry fintech \
  --max-results 100 \
  --objective find_companies
# → job_id: job:abc...

salva job status job:abc...
# → status: completed, run_id: run:xyz...

salva run show run:xyz... --json
```

### 3. REST API (HTTP clients, any language)

```bash
# Start the service
python3 -m uvicorn apps.api.main:app --port 8000

# Discover
curl -X POST http://localhost:8000/v1/discover \
  -H "Content-Type: application/json" \
  -d '{
    "objective": "find_companies",
    "intent": {
      "market": "Germany",
      "industry": "legal tech",
      "domain_hints": {
        "signal_terms": ["compliance", "e-signature"],
        "source_hints": ["law360.com", "legaltech.com"]
      }
    },
    "max_results": 20
  }'
```

---

## Cron / Scheduled Calls (Caller's Responsibility)

Salva does NOT own scheduling. If you need recurring execution:

```python
# In your agent / orchestrator:
import schedule
from salva_sdk import SalvaClient  # or call the REST API directly

client = SalvaClient(base_url="http://localhost:8000")

def weekly_market_scan():
    result = client.discover(
        market="Germany",
        industry="software",
        objective="find_market_activity",
    )
    # Act on result — store, alert, enrich, etc.

schedule.every().monday.at("09:00").do(weekly_market_scan)
```

Or from a cron job calling the CLI:

```bash
# crontab entry — Salva called as a skill, not a daemon
0 9 * * 1 salva find --market Germany --industry software --json >> ~/reports/weekly.jsonl
```

---

## Domain Hints — Per-Request Vocabulary Injection

Callers can inject custom vocabulary without modifying server code:

```json
{
  "objective": "find_companies",
  "intent": {
    "market": "US",
    "industry": "legal tech",
    "domain_hints": {
      "synonym_groups": {
        "contract": ["agreement", "NDA", "SLA", "MOU"]
      },
      "signal_terms": ["compliance", "e-signature", "regulatory"],
      "source_hints": ["law360.com", "legaltech.com", "g2.com"],
      "noise_terms": ["template", "sample", "boilerplate"]
    }
  }
}
```

For built-in domains (`events`, `bd_leads`, `companies`, `market_intel`,
`partnerships`, `general`), `domain_hints` extends the registry vocabulary —
it does not replace it. See `docs/domain-vocab-guide.md`.

---

## Async Job Pattern

For large searches or when you can't block:

```
1. salva_job_create(...)  →  job_id
2. [some time passes]
3. salva_job_status(job_id)  →  {status: "completed", run_id: "run:xyz"}
4. salva_run_result(run_id)  →  {entities: [...]}
5. salva_audit(run_id)       →  quality metrics
6. salva_pilot(run_id)       →  what to search next
```

Jobs require a worker process to execute:

```bash
# Start the worker (separate process)
python3 -m salva_core.worker

# Or use the API's inline execution (blocks until done)
curl -X POST http://localhost:8000/v1/jobs \
  -d '{"discovery": {...}, "wait_for_completion": true}'
```

---

## SSE Streaming (Long Jobs)

For real-time progress from long jobs via the REST API:

```bash
curl -N http://localhost:8000/v1/jobs/{job_id}/stream
```

Events are emitted per round. Each event is a JSON object with
`event_type`, `message`, and `data`. The stream ends when the job
reaches `completed` or `failed`.

SSE is for observability — Salva does not push unsolicited events.
