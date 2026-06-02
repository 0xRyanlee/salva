# Salva API 效果測試 & 優化建議

> 測試日期: 2026-05-09
> 方法: API/curl (MCP & Skill 未啟動)

---

## Raw Data

| ID | Topic | Objective | Market | Latency (ms) | Raw | Qualified | Rate | Issues |
|----|-------|-----------|-------|-------------|-----|-----------|------|--------|
| A | AI產品經理 | find_leads | 台灣 | 80,017 | 10 | 5 | 50% | 延遲高 |
| B | FinTech新創 | find_companies | 美國 | 43,637 | 20 | 4 | 20% | 結果錯位(台灣網站) |
| C | AI論壇峰會 | find_events | 歐洲 | 80,480 | 24 | 10 | 41.7% | 延遲高 |
| D | 區塊鏈合作 | find_partnership | 全球 | 12,863 | 25 | 4 | 16% | 合格率低 |
| E | 電商市場 | find_market_activity | 日本 | 72,198 | 25 | 6 | 24% | 延遲高 |

---

## 問題清單

### 問題 1: 結果錯位 (Topic B)
- **現象**: 搜尋"美國 FinTech"，但返回台灣網站 (ndc.gov.tw, moea.gov.tw)
- **可能原因**: 
  1. 市場關鍵字未正確傳遞給 provider
  2. Provider (SearXNG) 結果被當地化
  3. domain_vocab 映射錯誤

### 問題 2: 延遲過高 (Topic A, C, E)
- **現象**: 延遲 70-80 秒
- **可能原因**:
  1. 多輪檢索導致多次 API 呼叫
  2. Provider 響應慢
  3. 沒有使用 ANN 加速

### 問題 3: 合格率低 (Topic D)
- **現象**: 只有 16%
- **可能原因**:
  1. find_partnership 目標未正確配置 domain
  2. 關鍵字不夠精準
  3. 缺乏相關來源

---

## 優化建議清單

### P0 - 緊急

| # | 問題 | 建議動作 | 預期效果 |
|---|------|----------|----------|
| 1 | 結果錯位 | 檢查 OBJECTIVE_TO_DOMAIN 映射，新增 market_variants | 正確的市場結果 |
| 2 | Provider 超時 | 實現 timeout + retry 機制 | 降低延遲 |

### P1 - 高優先

| # | 問題 | 建議動作 | 預期效果 |
|---|------|----------|----------|
| 3 | 多輪延遲 | 啟用 ANN 搜尋 (SALVA_USE_ANN_SEARCH=true) | 加速 50%+ |
| 4 |合格率低 | 擴展 domain_vocab 的 source_hints | 提高命中率 |

### P2 - 中優先

| # | 問題 | 建議動作 | 預期效果 |
|---|------|----------|----------|
| 5 | 結果單一 | 增加 provider fallback 鏈 | 更多來源 |
| 6 | 缺少維度 | 新增 market 維度的量化指標 | 追蹤改善 |

---

## 測試方法限制

- ❌ MCP Server: 啟動失敗 (端口綁定問題)
- ❌ Skill: 未配置
- ✅ API/curl: 正常運行

**建議**: 修復 MCP 後重新測試矩陣對比