# Experiment: hypergraph vs binary ownership penetration

Prove-first experiment for Salva's commercial-entity-intelligence direction.
Tests one falsifiable claim:

> **A typed n-ary hypergraph (role + arity + evidence) preserves control facts
> that a binary FtM-style decomposition loses — so penetration is more correct,
> not just prettier.**

## Run

```bash
python -m experiments.hg_penetration.run
```

No dependencies (stdlib `sqlite3`). Runs in the repo venv.

## What it shows (honest result)

On an illustrative ownership structure where TargetCo is controlled by a
**75% acting-in-concert bloc** (30% + 25% + 20%, no single majority):

| | control conclusion | effective ownership |
|---|---|---|
| **Hypergraph** (concert-aware) | **controlled by 75% concert bloc** ✓ | Person A 42% … |
| **FtM binary** | **"no controlling shareholder"** ✗ | Person A 42% … (same) |

- **Differentiator = the n-ary "acting-in-concert" fact.** It lives on one
  hyperedge; binary decomposition has nowhere to put a group-level property, so
  the controlling bloc becomes invisible and penetration mis-reports "no control".
- **Honesty:** layered *effective ownership* is identical in both — chained
  percentage layering works fine with binary edges. It is **not** a differentiator.
  Multi-role events (acquirer/seller/advisor) also shatter into disconnected
  binary links — coherence lost.

This isolates the **representation** variable (synthetic data with controlled
structure). It does **not** yet test data acquisition.

## Design

- `store.py` — typed n-ary incidence hypergraph on SQLite
  (`nodes / hyperedges / incidences(role, percentage, order_index) / evidence`).
  The incidence table *is* the hypergraph; not a property graph pretending.
- `seed_data.py` — illustrative dataset + **Jurisdiction Source Registry** seed.
- `penetrate.py` — n-ary, concert-aware control analysis + layered effective ownership.
- `ftm_baseline.py` — decompose to binary edges; same penetration without concert semantics.
- `run.py` — compare + verdict + show the source registry.

### Jurisdiction Source Registry (self-optimisation substrate)

`(jurisdiction, fact_type) → ranked public sources {source, access, reliability, legal_availability}`.
`legal_availability` is first-class: the pipeline only routes to lawful public
sources by design (e.g. TW private-company full shareholder rosters are **not**
public under 公司法 §210 → not routable). This seed is what `source_attempts`
telemetry would later re-rank — the concrete, honest form of "the pipeline learns
which source works for which jurisdiction/fact, so future searches have a path to choose."

Seeded: CN (gsxt + aggregators + news), TW listed (MOPS) / private (商工登記/TDCC),
US (SEC EDGAR + state), UK (Companies House PSC).

## Next increments (not done here)

1. **Real acquisition probe** — can the open web reliably yield equity facts for
   CN/TW real companies? (the "data death-valley" risk). Feed `source_attempts`.
2. Wire `source_attempts` → re-rank the registry (prove the routing *learns*).
3. HIF export; bipartite/star projection for a viz window.
