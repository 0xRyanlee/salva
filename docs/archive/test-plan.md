# Salva Runtime 測試規劃

> 設計不同深度廣度的檢索需求，規劃多輪調研路徑

## 測試方法

### 調用方式對比

| 方式 | 指令範例 | 用途 |
|------|----------|------|
| **curl** | `curl -X POST http://localhost:8000/v1/discover` | 直接 API 測試 |
| **skill** | `/salva discover --objective find_leads --market 台灣` | OpenClaw agent 調用 |
| **MCP** | `salva_discover(...)` | Claude/Cody 等 AI 工具 |

### 測試策略

- **淺層 (Shallow)**: 1-2 輪，快速掃描
- **中等 (Medium)**: 2-3 輪，dive + anchor
- **深層 (Deep)**: 4+ 輪，完整的多階段調研

---

## 測試案例設計

### 案例 1: 台灣 AI 產品經理職缺 (淺層)

**目標**: find_leads  
**市場**: 台灣  
**產業**: AI人工智慧  
**策略**: anchor (2 輪)

| 輪次 | 目標 | 關鍵詞 | 預期結果 |
|------|------|--------|----------|
| R1 | 廣泛搜尋 | "產品經理" "AI" "台灣" | 收集候選頁面 |
| R2 | 精準篩選 | "AI產品經理" "徵才" "職缺" | 过滤出 LinkedIn 職缺 |

---

### 案例 2: 美國 FinTech 新創 (中等)

**目標**: find_companies  
**市場**: 美國  
**產業**: FinTech  
**策略**: dive + anchor (3 輪)

| 輪次 | 目標 | 關鍵詞 | 預期結果 |
|------|------|--------|----------|
| R1 | 精準搜尋 | "FinTech startup" "Series A" "USA" | 找到投資相關新創 |
| R2 | 擴展搜尋 | "FinTech" "USA" "new startup" | 擴展更多新創 |
| R3 | 驗證確認 | "FinTech USA funding" | 驗證公司存在 |

---

### 案例 3: 歐洲 AI 論壇峰會 (深層)

**目標**: find_events  
**市場**: 歐洲  
**產業**: AI人工智慧  
**策略**: radar + anchor + dive (4 輪)

| 輪次 | 目標 | 關鍵詞 | 預期結果 |
|------|------|--------|----------|
| R1 | 雷達掃描 | "AI conference" "Europe" "2024" | 廣泛收集會議 |
| R2 | 錨定關鍵 | "AI summit" "Europe" "machine learning" | 精準會議 |
| R3 | 深入挖掘 | "AI conference" "2024" "registration" | 取得報名資訊 |
| R4 | 確認細節 | "AI summit Europe" "agenda" "speakers" | 完整議程 |

---

### 案例 4: 全球區塊鏈合作信號 (深層)

**目標**: find_partnership_signals  
**市場**: 全球  
**產業**: 區塊鏈  
**策略**: anchor + radar + dive (4 輪)

| 輪次 | 目標 | 關鍵詞 | 預期結果 |
|------|------|--------|----------|
| R1 | 尋找信號 | "blockchain partnership" "announcement" | 合作新聞 |
| R2 | 擴展來源 | "blockchain" "strategic partnership" "2024" | 更多來源 |
| R3 | 公司驗證 | "blockchain partnership" "company name" | 確認公司 |
| R4 | 深入細節 | "blockchain" "joint venture" "token" | 合作細節 |

---

### 案例 5: 日本電商市場趨勢 (中等)

**目標**: find_market_activity  
**市場**: 日本  
**產業**: 電商  
**策略**: dive + anchor (3 輪)

| 輪次 | 目標 | 關鍵詞 | 預期結果 |
|------|------|--------|----------|
| R1 | 精準搜尋 | "ecommerce Japan" "market size" | 市場規模 |
| R2 | 趨勢擴展 | "ec site" "Japan" "growth" | 成長趨勢 |
| R3 | 確認來源 | "日本 電商 市場 報告" | 確認資料來源 |

---

### 案例 6: 英國 Product Manager (淺層)

**目標**: find_leads  
**市場**: 英國  
**產業**: 科技  
**策略**: anchor (2 輪)

| 輪次 | 目標 | 關鍵詞 | 預期結果 |
|------|------|--------|----------|
| R1 | 搜尋職缺 | "Product Manager" "UK" "hiring" | LinkedIn 職缺 |
| R2 | 精準篩選 | "Product Manager" "London" "tech" | 倫敦科技職缺 |

---

### 案例 7: 新加坡 SaaS 公司 (深層)

**目標**: find_companies  
**市場**: 新加坡  
**產業**: SaaS  
**策略**: dive + anchor + radar (4 輪)

| 輪次 | 目標 | 關鍵詞 | 預期結果 |
|------|------|--------|----------|
| R1 | 精準定位 | "SaaS company" "Singapore" "B2B" | 當地 SaaS |
| R2 | 擴展範圍 | "cloud service" "Singapore" "enterprise" | 雲端服務 |
| R3 | 雷達掃描 | "Singapore" "software" "startup" | 新創軟體 |
| R4 | 深度確認 | "SaaS Singapore" "founder" "funding" | 創辦人/融資 |

---

### 案例 8: 全球資安經銷商 (中等)

**目標**: find_leads  
**市場**: 全球  
**產業**: 資訊安全  
**策略**: anchor + dive (3 輪)

| 輪次 | 目標 | 關鍵詞 | 預期結果 |
|------|------|--------|----------|
| R1 | 搜尋經銷 | "security reseller" "distribution" "global" | 經銷商名單 |
| R2 | 精準確認 | "cybersecurity distributor" "partner" | 資安經銷 |
| R3 | 公司驗證 | "security company" "distribution partner" | 驗證公司 |

---

### 案例 9: 台灣醫療器材 (淺層)

**目標**: find_companies  
**市場**: 台灣  
**產業**: 醫療器材  
**策略**: dive (2 輪)

| 輪次 | 目標 | 關鍵詞 | 預期結果 |
|------|------|--------|----------|
| R1 | 搜尋公司 | "醫療器材" "台灣" "公司" | 醫材公司 |
| R2 | 展會確認 | "醫療器材" "台灣" "展覽" | 相關展會 |

---

### 案例 10: 美國社交媒體 AI 市場 (深層)

**目標**: find_market_activity  
**市場**: 美國  
**產業**: AI + 社交媒體  
**策略**: radar + anchor + dive + deep (5 輪)

| 輪次 | 目標 | 關鍵詞 | 預期結果 |
|------|------|--------|----------|
| R1 | 市場雷達 | "AI social media" "USA" "market" | 市場趨勢 |
| R2 | 錨定產品 | "AI feature" "social platform" "USA" | AI 功能 |
| R3 | 深入應用 | "generative AI" "social media" "USA" | 生成式 AI |
| R4 | 公司確認 | "AI social media startup" "USA" | 新創公司 |
| R5 | 深度分析 | "AI social media" "revenue" "user growth" | 營收/用戶 |

---

## 執行順序

1. **淺層測試** (1-2 輪): 案例 1, 6, 9
2. **中等測試** (3 輪): 案例 2, 5, 8
3. **深層測試** (4-5 輪): 案例 3, 4, 7, 10

---

## 預期輸出格式

每個測試案例應輸出：
- Qualified count / Raw count
- 每輪使用的策略和關鍵詞
- 找到的 entities 列表
- 分析失敗原因（如果有）

---

## 整合測試 (2026-05-09 更新)

真實 API/MCP/Skill 調用測試已實現：

**檔案**: `tests/test_integration_real_calls.py`

**執行方式**:
```bash
# 1. 啟動 API
python3 -m uvicorn apps.api.main:app --port 8000

# 2. 執行測試
python3 -m pytest tests/test_integration_real_calls.py -v

# 或使用腳本
./run_integration_tests.sh
```

**測試類別**:
- TestRestApiDiscover - /v1/discover 同步發現
- TestRestApiJobs - /v1/jobs 異步作業
- TestRestApiQueries - 列表查詢端點
- TestMcpIntegration - MCP 工具
- TestSkillIntegration - Skill 端到端
- TestMatrixCombinations - objective/market/industry 矩陣
- TestEdgeCases - 邊界情況