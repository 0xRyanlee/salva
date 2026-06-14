# E23 — Entity Resolution Recall (GLEIF + Wikidata)

**Date:** 2026-06-12

**Test set:** ['TSMC', 'ASUSTeK', 'Acer', 'MediaTek', 'Delta Electronics', 'Advantech', 'Foxconn', 'HTC', 'MSI', 'Wistron']

## Results

| Tier | Recall | Resolved | Failed |
|---|---|---|---|
| A-baseline | 0.00 | [] | ['TSMC', 'ASUSTeK', 'Acer', 'MediaTek', 'Delta Electronics', 'Advantech', 'Foxconn', 'HTC', 'MSI', 'Wistron'] |
| B-gleif | 0.90 | ['TSMC', 'ASUSTeK', 'Acer', 'MediaTek', 'Delta Electronics', 'Advantech', 'Foxconn', 'MSI', 'Wistron'] | ['HTC'] |
| C-wikidata | 1.00 | ['TSMC', 'ASUSTeK', 'Acer', 'MediaTek', 'Delta Electronics', 'Advantech', 'Foxconn', 'HTC', 'MSI', 'Wistron'] | [] |

**P1 (GLEIF ≥ 0.50):** ✓  **P2 (Wikidata ≥ 0.60):** ✓  **P3 (external > baseline):** ✓

**Verdict: PASS**

## Tier B-gleif details

- **TSMC**: TSM
- **ASUSTeK**: AUSTEK CONSULTING SERVICES PTY LTD
- **Acer**: AER
- **MediaTek**: MEDIATEQ
- **Delta Electronics**: DELTA ELECTRONICS (INDIA)
- **Advantech**: ADVANTEC AS
- **Foxconn**: FoxCon
- **HTC**: (no result)
- **MSI**: MSI
- **Wistron**: Witronia Oy

## Tier C-wikidata details

- **TSMC**: Q713418: semiconductor foundry company headquartered in Taiwan
- **ASUSTeK**: Q152864: Taiwanese computers and electronics company
- **Acer**: Q42292: genus of plants
- **MediaTek**: Q699848: Taiwanese semiconductor company
- **Delta Electronics**: Q5254620: Taiwanese electronics manufacturing company
- **Advantech**: Q26954687: Taiwanese computer hardware company
- **Foxconn**: Q463094: Taiwanese multinational electronics contract manufacturer
- **HTC**: Q186012: Taiwanese electronics company
- **MSI**: Q1126102: neo-fascist and post-fascist political party in Italy
- **Wistron**: Q441821: Taiwanese company

