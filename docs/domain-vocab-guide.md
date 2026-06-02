# Domain Vocabulary Guide

Salva's query intelligence uses a domain vocabulary system to expand searches
with relevant signal terms, source hints, and synonym groups.

---

## Built-in Domains

The registry (`core/domain_vocab.py`) ships with 6 built-in domains:

| Domain | Objective | What it knows |
|--------|-----------|---------------|
| `events` | `find_events`, `find_exhibitors` | Conference/meetup sites, date signals, venue terms |
| `bd_leads` | `find_leads` | B2B directory sites, partner/reseller signals |
| `companies` | `find_companies` | Company DB sites, funding signals, team/product terms |
| `market_intel` | `find_market_activity` | News/analyst sites, trend signals, competitor terms |
| `partnerships` | `find_partnership_signals` | Partnership announcement signals, co-marketing terms |
| `general` | any unmapped objective | Generic fallback — no industry assumptions |

`general` is the fallback for any unknown domain or objective. It uses only
the caller's `primary_terms` with no industry-specific expansion.

---

## Inspect Built-in Vocabularies

```bash
# List all domains
salva vocab list

# See full vocabulary for a domain
salva vocab show companies

# JSON output for programmatic use
salva vocab show events --json
```

---

## Injecting Custom Vocabulary Per Request

Callers can extend or override the built-in vocabulary per request
via `domain_hints`. This is the recommended way to handle specialized
domains without modifying server code.

### Via REST API

```json
{
  "objective": "find_companies",
  "intent": {
    "market": "US",
    "industry": "legal tech",
    "domain_hints": {
      "synonym_groups": {
        "contract": ["agreement", "NDA", "SLA", "MOU"],
        "legaltech": ["legal software", "law tech", "legal AI"]
      },
      "signal_terms": ["compliance", "e-signature", "regulatory", "matter management"],
      "source_hints": ["law360.com", "legaltech.com", "g2.com", "capterra.com"],
      "noise_terms": ["template", "sample form", "boilerplate"]
    }
  }
}
```

### Via MCP (Claude Code)

Pass `domain_hints_json` as a JSON string:

```
salva_discover(
  market="US",
  industry="legal tech",
  domain_hints_json='{"signal_terms": ["compliance", "e-signature"], "source_hints": ["law360.com"]}'
)
```

### Via CLI

```bash
salva find \
  --market US \
  --industry "legal tech" \
  --domain-hints '{"signal_terms": ["compliance", "e-signature"]}'
```

---

## How domain_hints Merges with the Registry

`domain_hints` **extends** the registry vocabulary, it does not replace it.

```
final_vocab = registry_vocab(domain).merge(domain_hints)
```

- `signal_terms`: extended, deduplicated
- `source_hints`: extended, deduplicated
- `synonym_groups`: extended (new keys added; existing keys not overwritten)
- `noise_terms`: extended, deduplicated
- `region_variants`: extended

---

## Registering a New Domain at Runtime

For persistent custom domains (e.g., an internal team always searches legal tech):

```python
from core.domain_vocab import DomainVocab, register_domain

register_domain("legaltech", DomainVocab(
    signal_terms=["compliance", "e-signature", "contract management", "matter"],
    source_hints=["law360.com", "legaltech.com", "g2.com/categories/legal"],
    synonym_groups={
        "legaltech": ["legal software", "law tech", "legal AI"],
        "contract":  ["agreement", "NDA", "SLA"],
    },
    noise_terms=["template", "sample", "boilerplate"],
))
```

After registration, requests with `objective: "find_legaltech"` (or explicit
`domain: "legaltech"` on the Intent) will use this vocabulary automatically.

To persist across restarts, call `register_domain()` in an app startup hook.

---

## domain vs. objective Mapping

The service maps each `objective` to a domain automatically:

| objective | domain |
|-----------|--------|
| `find_events` | `events` |
| `find_exhibitors` | `events` |
| `find_leads` | `bd_leads` |
| `find_companies` | `companies` |
| `find_market_activity` | `market_intel` |
| `find_partnership_signals` | `partnerships` |
| *(anything else)* | `general` |

For custom objectives, pass `domain_hints` to inject the right vocabulary
rather than defining a new objective.

---

## When to Use domain_hints vs. Registering a Domain

| Scenario | Recommendation |
|----------|---------------|
| One-off search in an unfamiliar domain | `domain_hints` per request |
| Team always searches the same domain | `register_domain()` at startup |
| Extending an existing domain for one search | `domain_hints` (merges with registry) |
| Building a product-specific Salva deployment | `register_domain()` + custom pyproject extras |
