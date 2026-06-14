# E8 findings — HIF projection + bipartite visual window (VP8)

`python -m experiments.hg_penetration.e8_hif_projection`

## Fixture

Chatham Lodging Trust §13(d)(3) concert group (from E3). 5 nodes, 1 hyperedge, 5 incidences, 1 evidence.

## [A] HIF round-trip: **PASS**

Zero diff between original and re-imported store across all tables.
HIF exchange format is lossless for this schema.


## [B] Bipartite incidence list

| node | hyperedge | role |
|---|---|---|
| `chatham` | `he_concert_1` | `target` |
| `bluemountain` | `he_concert_1` | `group_lead` |
| `bm_fund_a` | `he_concert_1` | `group_member` |
| `bm_fund_b` | `he_concert_1` | `group_member` |
| `bm_fund_c` | `he_concert_1` | `group_member` |

## [C] Star projection (pairwise via shared hyperedge)

| entity A | entity B | shared edge | co-memberships |
|---|---|---|---|
| `bluemountain` | `bm_fund_a` | `he_concert_1` | 1 |
| `bluemountain` | `bm_fund_b` | `he_concert_1` | 1 |
| `bluemountain` | `bm_fund_c` | `he_concert_1` | 1 |
| `bluemountain` | `chatham` | `he_concert_1` | 1 |
| `bm_fund_a` | `bm_fund_b` | `he_concert_1` | 1 |
| `bm_fund_a` | `bm_fund_c` | `he_concert_1` | 1 |
| `bm_fund_a` | `chatham` | `he_concert_1` | 1 |
| `bm_fund_b` | `bm_fund_c` | `he_concert_1` | 1 |
| `bm_fund_b` | `chatham` | `he_concert_1` | 1 |
| `bm_fund_c` | `chatham` | `he_concert_1` | 1 |

## Verdict

- **Confirmed:** incidence hypergraph exports losslessly to HIF JSON and re-imports with zero diff — the store is not a black box.
- Bipartite and star projections are trivially computable from the incidence table.
- This confirms VP8: canonical incidence → HIF round-trip + projectable.

## Development implication

The HIF export function (`export_hif`) is production-ready and can be wired into `salva_core/persistence/` as an export API. The star projection is the natural way to render the graph to a frontend or agent.
