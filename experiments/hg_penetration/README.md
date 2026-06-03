# Experiment: hypergraph vs binary ownership penetration

Prove-first experiment for Salva's commercial-entity-intelligence direction.
Tests one falsifiable claim:

> **A typed n-ary hypergraph (role + arity + evidence) preserves control facts
> that a binary FtM-style decomposition loses — so penetration is more correct,
> not just prettier.**

## Run

```bash
python -m experiments.hg_penetration.run          # synthetic: hypergraph vs binary penetration
python -m experiments.hg_penetration.probe_sec    # data probe: SEC equity-fact availability
python -m experiments.hg_penetration.run_real      # REAL: SEC group → n-ary hyperedge + routing learns
```

Stdlib only (`sqlite3`, `urllib`). `probe_sec` / `run_real` need network (SEC EDGAR).

### Real end-to-end (`run_real.py`)

- **Part 1** acquires a real SEC SC 13D **group** filing (e.g. Chatham Lodging
  Trust, a 15-entity BlueMountain §13(d)(3) group, 2013), extracts the reporting
  persons from the cover pages, and builds **one n-ary concert hyperedge** with
  the SEC URL as evidence. Binary decomposition turns it into 15 "independent"
  minority holders — the coordinated-group fact is lost.
- **Part 2** records real `source_attempts` and re-ranks the registry: US SEC
  EDGAR is boosted (real hit), **CN gsxt is demoted below aggregators/news after
  a real failed automated attempt** (anti-bot). The route map *self-optimises* —
  authority ≠ reachability, and the pipeline learns the difference.

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

## Increments

- [x] Representation: hypergraph vs binary penetration (`run.py`).
- [x] Data probe: SEC equity-fact availability (`probe_sec.py`, `PROBE_FINDINGS.md`).
- [x] Real acquisition: SEC SC 13D group → n-ary hyperedge with evidence (`run_real.py`).
- [x] `source_attempts` → registry re-rank (routing learns; `routing.py`).
- [ ] CN/TW real listed acquisition (MOPS / cninfo / Tushare).
- [ ] HIF export; bipartite/star projection for a viz window.
- [ ] Cross-source entity resolution (reuse Nomenklatura/Yente).
