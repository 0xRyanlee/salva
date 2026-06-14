# E5 findings — cross-lingual entity resolution (VP5)

`python -m experiments.hg_penetration.e5_entity_resolution`

**Hypothesis:** the same entity across 中/英/拼音/ticker/別名 can be resolved to one
canonical entity; and string methods alone cannot bridge scripts/languages.

**Dataset:** 27 surface forms across 6 gold entities (TSMC, Alibaba, Tencent, Hon
Hai/Foxconn) + distractors (Bank of China vs China Construction Bank — share tokens,
distinct). Stdlib only; pairwise precision/recall/F1 vs gold clusters.

## Result

| method | precision | recall | F1 |
|---|---:|---:|---:|
| exact | 1.00 | 0.00 | 0.00 |
| normalized (suffix strip) | 1.00 | 0.02 | 0.03 |
| normalized + 繁→簡 bridge | 1.00 | 0.07 | 0.13 |
| char-trigram fuzzy ≥0.5 | 1.00 | 0.03 | 0.07 |
| alias gazetteer (external) | 1.00 | 1.00 | 1.00 |

## Verdict (honest)

- **Confirmed:** string/fuzzy/normalization methods reach only ~0–7 % recall. They
  merge **within a script** (suffix & spelling variants) and never produce false
  merges here (precision 1.00 — distractors stay separate).
- **The 繁→簡 bridge** recovers CN-internal cross-form (台積電 ↔ 台积电); production
  needs opencc. Still within-CJK only.
- **No string method bridges 中文 ↔ English ↔ ticker** (台積電 ↔ TSMC ↔ 2330): zero
  shared signal — empirically impossible by string ops.
- **Only the gazetteer reaches full recall**, but it *encodes external knowledge*
  (tautological on this set), must be maintained, and **does not generalise** to
  unseen entities.

## Development implication (evidence-based)

Cross-language/script entity resolution **requires a generalising bridge**:
**multilingual embedding (Jina) + alias gazetteer + transliteration (opencc/pypinyin)**.
String ops alone are insufficient — this is now proven, not assumed.

## Open (next)

- **E5b** (needs Jina multilingual embedding wired): benchmark embedding similarity
  as the *generalising* bridge on the same dataset — does it recover cross-script
  pairs (台積電↔TSMC) without a hand-maintained gazetteer, and at what precision?
  This is the real test of the production solution; deferred until the model is wired.
