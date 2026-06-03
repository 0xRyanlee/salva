# E6 findings — cross-semantic relation/fact merging (VP6)

`python -m experiments.hg_penetration.e6_relation_merge`

**Hypothesis:** equivalent relations/roles across languages normalise to one
schema; multi-source records of the same fact merge into one hyperedge with
multiple evidence (provenance kept, conflicts surfaced); distinct relations are
not over-merged.

**Dataset:** 7 raw multilingual source records (gsxt/news/filing/mops) covering
one ownership fact phrased 4 ways (持股 / owns / 控股 / holds stake in, incl. a 70%
vs 65% conflict), one directorship (董事長 / chairman), and one distinct 投資 fact.

## Result

| | facts |
|---|---|
| naive (raw surface keys) | **7** (fragmented; 持股/owns/控股 look like 3 relations) |
| normalised + merged | **3** canonical hyperedges |

- `ownership(holdco_a → target_b)` — **4 evidence** merged, **70% vs 65% conflict surfaced** (not overwritten).
- `directorship(zhang_san → target_b)` — 2 evidence (董事長 + chairman).
- `investment(holdco_a → c_co)` — kept **separate** (投資 ≠ ownership; no over-merge).

## Verdict (honest)

- **Confirmed:** a curated relation ontology (FtM-aligned) + the E5 entity bridge
  collapses multilingual same-fact records into one canonical hyperedge, with all
  provenance preserved and value conflicts flagged rather than silently lost.
- Semantic distinctions are preserved (投資 not merged into ownership).
- **Limit (same as E5):** relies on a curated ontology + entity gazetteer for known
  terms; unseen phrasings need multilingual embedding / LLM normalisation.

## Development implication (evidence-based)

Build a **canonical relation ontology as data** (FtM-aligned: ownership /
directorship / investment … with roles + arity), compose with the E5 entity
bridge, and use a **conflict-preserving merge** keyed on `(subject_id,
canonical_relation, object_id)`. Embedding/LLM normalisation handles the long tail.
