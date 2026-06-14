# E5b findings — Jina multilingual embedding cross-lingual bridge (VP5)
`python -m experiments.hg_penetration.e5b_jina_benchmark`
**Model:** `jina-embeddings-v5-text-small-retrieval-mlx` via omlx (1024d)
**Dataset:** 27 surface forms across 6 gold entities (same as E5)

## Cross-script similarity spotlight
| pair | cosine | gold |
|---|---:|---|
| `台積電` ↔ `TSMC` | 0.0384 | SAME |
| `台積電` ↔ `2330.TW` | 0.4832 | SAME |
| `TSMC` ↔ `2330.TW` | 0.0213 | SAME |
| `台積電` ↔ `台积电` | 0.9989 | SAME |
| `鴻海` ↔ `Foxconn` | 0.3021 | SAME |
| `阿里巴巴` ↔ `BABA` | 0.0415 | SAME |
| `腾讯` ↔ `TCEHY` | 0.0222 | SAME |
| `中国银行` ↔ `中国建设银行` | 0.6170 | DIFF |

## Best threshold result
Threshold **0.40** → precision 0.44 / recall 0.24 / **F1 0.31**

## Verdict (FAIL)
- **Not confirmed:** Jina embedding alone does not reliably bridge cross-script pairs at F1 ≥ 0.80 (achieved 0.31).
- Gazetteer + transliteration (opencc/pypinyin) remain required as primary bridge.
- Embedding can serve as a secondary heuristic only.
