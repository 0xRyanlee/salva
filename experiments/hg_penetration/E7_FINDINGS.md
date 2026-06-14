# E7 findings — Semantic graph search + 2-hop traversal (VP7)

`python -m experiments.hg_penetration.e7_semantic_search`

**Model:** `jina-embeddings-v5-text-small-retrieval-mlx` (1024d)

## Method

Synthetic 12-node, 4-hyperedge graph. Baseline: keyword token overlap. Semantic: Jina cosine top-3 + 2-hop hyperedge traversal.

## Results

| query | method | P | R | F1 |
|---|---|---:|---:|---:|
| US semiconductor equity holding | keyword | 0.80 | 0.80 | 0.80 |
| | semantic @3 | 0.67 | 0.40 | 0.50 |
| | sem+2hop | 0.56 | 1.00 | 0.71 |
| semiconductor supply chain foundry | keyword | 0.75 | 0.60 | 0.67 |
| | semantic @3 | 1.00 | 0.60 | 0.75 |
| | sem+2hop | 0.56 | 1.00 | 0.71 |
| Swiss pharmaceutical company | keyword | 1.00 | 1.00 | 1.00 |
| | semantic @3 | 0.67 | 1.00 | 0.80 |
| | sem+2hop | 0.33 | 1.00 | 0.50 |
| ARM IPO investor SoftBank | keyword | 0.75 | 0.75 | 0.75 |
| | semantic @3 | 0.67 | 0.50 | 0.57 |
| | sem+2hop | 0.44 | 1.00 | 0.62 |

## Verdict: **INCONCLUSIVE**

Semantic+2hop did not consistently outperform keyword (1/4).
Likely cause: node labels are too short and semantically dense for the embedding model to reliably distinguish. Longer, more descriptive labels would improve recall.
Keyword baseline is surprisingly competitive on a small, structured graph.

## Development implication

Enrich node labels with more context (company descriptions, sectors, regions). Alternatively, embed full evidence snippets, not just node labels.
