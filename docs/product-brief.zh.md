# Salva 產品簡介

Salva 是一個自架的 discovery intelligence runtime。它不是單次搜尋工具，也不是爬蟲包裝，而是一個把「檢索、路由、超圖、證據、記憶、審計、租戶邊界」整合在一起的可重用系統。

這份文件是介紹性簡報，不是 PRD，也不是正式契約。正式行為請看 `docs/spec/`。

## 核心定位

- 面向 agent、CLI、MCP、SDK 與 REST caller
- 以結構化 intent 作為入口
- 以 experience profile 決定檢索路徑
- 以 multi-round retrieval + graph expansion 逐步累積信號
- 以 query-family memory 讓後續 run 更準
- 以超圖把 run、entity、relation、evidence、source 串成可走訪的研究結構

## ⚠️ 待 owner 拍板：定位論述與 Phase 3 實測數據的落差

本文件下方「為什麼比直接搜尋更有效」與「和其他工具的對比」兩節，寫作時間早於 2026-07-03 的 Phase 3 嚴謹對照實驗（18 題固定任務集，`experiments/salva_v2/ANALYSIS_FINDINGS.md`）。Phase 3 的核心發現：

- **純檢索/找到正確答案的能力**：Arm A（裸 Claude Code + Haiku）vs Arm B（+Salva）在 18 題上是 **17 平手、Arm B 贏 1、Arm A 贏 0**——不是 Salva 更準，是因為 agent 允許在 Salva 沒用時退回裸搜尋，這才是真實 production 行為。
- **Salva 自己的評分/篩選層在 61%（11/18）的測試裡回傳零可用實體**，即使 `retrieval_health` 100% 正常——問題不在檢索或 provider 健康，在 `QualificationScorer` 的評分邏輯。
- 下方「效果對比」段落引用的「3 組本地比較樣本」是更早、規模小很多的另一次測試（非公開資料集、無 ground truth 核驗），不是 Phase 3 這批有人工核驗 ground truth 的數據，兩者不應該被讀成同一件事的佐證。

這對定位論述造成的實際張力：本文件目前把 Salva 定位成「比直接搜尋更有效」的替代品，但 Phase 3 目前的證據支持的比較接近「跟裸 agent 打平手、在部分場景（中文關鍵字實體查詢）更有效率」，不是全面優於裸搜尋。以下選項留給 owner 決定，我不自行改寫下方定位措辭：

- **選項 1 — 維持現有定位**（取代/優於直接搜尋）：目前 Phase 3 數據不支持，除非用更大規模實驗、或先修好 `QualificationScorer` 篩選層再重測後有更強證據。
- **選項 2 — 改為「結構化沉澱層」定位**（裸搜尋之上/之後的加值層，而非替代品）：Phase 3 數據較支持——route/pilot/audit/hypergraph/memory 這些「結構化」賣點 Phase 3 完全沒測到（也沒被推翻），且 Arm B 確實有一個真實但溫和的效率優勢（總請求數少 14%）。這個框架下，「為什麼比直接搜尋更有效」整節需要重寫成「Salva 補足了直接搜尋缺的哪些結構」，而不是暗示找到答案的能力本身更強。
- **選項 3 — 縮小效果宣稱的範圍**：只針對 Phase 3 數據明確支持的場景（中文關鍵字公司查詢、成本效率）做宣稱，其餘場景（單一英文實體查詢、多跳關係查詢）誠實標示「與裸搜尋打平，尚待評分層修復後重新驗證」。

完整數據見 `experiments/salva_v2/ANALYSIS_FINDINGS.md`（含三張圖表）。

## 先看亮點

- **智能路由**：不是所有問題都走同一條路；Salva 會先決定該用 `quick_scan`、`lead_focus`、`company_research`、`deep_investigation`，還是 `platform_integrator`。
- **多工具並發**：當信號品質不夠好，Salva 不會只守著一個來源，而是能擴成多 provider fallback / merge。
- **深度挖掘**：它不是只回答第一輪，而是會用 `pilot`、`mate`、`audit` 把下一輪和後續價值一起拉出來。
- **超圖沉澱**：`run` 不是垃圾資料；它會留下 `entity`、`relation`、`evidence`、`hyperedge`，後面可以 walk、查、比、重用。
- **越用越準**：`query-family memory` 讓同類問題不斷累積信號，而不是每次都從零開始。

## 主要亮點

### 1. 不是單次查詢，而是可複利的檢索管線

一般搜尋工具只回答「這一次找到了什麼」。Salva 還會回答：

- 這次應該走哪個 route
- 下一輪該搜什麼
- 哪些 source 最有信號
- 這一類查詢之後可不可以越查越準

這表示它不是一個 endpoint，而是一個會隨使用次數變強的流程。對 vibe coder 來說，最簡單的理解是：先問系統「怎麼打」，再讓系統幫你打，最後把結果變成下一輪的起點。

### 2. 對 agent 友好的決策面

Salva 有明確的索引層：

- `GET /v1/routes`
- `POST /v1/experience-plan`
- `POST /v1/pilot`
- `GET /v1/providers/catalog`
- `GET /v1/hold/backends`
- `GET /v1/semantic/indexes`

agent 不需要猜整個系統怎麼跑，可以先讀索引，再選路徑。

### 2.5 不是單工具，而是工作流底座

你可以把 Salva 想成這個順序：

1. 先選 route
2. 再跑 retrieval
3. 再看 evidence
4. 再用 `pilot` 決定下一輪
5. 再用 `hold` / `semantic memory` / `audit` 做沉澱

這是它和一般 API / CLI 最大的不同。

### 3. 結構化輸出，不只是 URL 列表

Salva 回傳的是：

- entities
- relations
- telemetry
- evidence
- run meta
- job state

這讓它更像一個 research runtime，而不是 search wrapper。

### 4. 明確的 tenant / quota / error contract

系統已經內建：

- tenant scope
- usage telemetry
- quota / rate-limit
- HTTP / MCP / job 錯誤契約

這使它能進入團隊內部共享使用，而不是只適合個人腳本。

## 功能總覽

### 檢索層

- `POST /v1/discover`：同步 discovery
- `POST /v1/jobs`：背景任務
- `GET /v1/routes`：route catalog
- `POST /v1/pilot`：下一步檢索建議
- `POST /v1/mate/{run_id}`：成本 / 時間 / tokens 節省估算

### 可觀測層

- `GET /v1/usage`
- `GET /v1/quota`
- `GET /v1/audits/{run_id}`
- `GET /v1/snapshots/{run_id}`
- `GET /v1/relations`
- `GET /v1/evidence/*`

### 圖與記憶層

- `GET /v1/hold/backends`
- `GET /v1/hold/walk`
- `GET /v1/semantic/indexes`
- `query-family memory`

### 路由模式

- `quick_scan`：一輪快速回答
- `lead_focus`：先精準，再擴展
- `company_research`：平衡回收率與結構化
- `deep_investigation`：深入挖掘、逐步擴散
- `platform_integrator`：契約先行，面向 agent / downstream consumer

### 整合層

- MCP
- CLI
- Python SDK
- REST API

## 怎麼用

### 1. 快速查找

適合單輪、低成本、先看大致方向。

```json
POST /v1/discover
{
  "objective": "find_leads",
  "intent": {
    "market": "Germany",
    "industry": "software"
  },
  "max_results": 20,
  "output_profile": "lead"
}
```

### 2. 背景調研

適合需要更多輪次、更多信號、更多證據的任務。

- 用 `POST /v1/jobs`
- 跑完後用 `GET /v1/jobs/{id}`
- 再接 `POST /v1/pilot`

### 3. 路由先看，再決定要不要跑

如果 caller 不確定該走哪條路，先讀：

- `GET /v1/routes`
- `POST /v1/experience-plan`

這比直接塞一個大而全的 prompt 更穩。

### 4. 想做完整課題研究

適合這種模式：

- 先跑 `find_market_activity` 或 `find_companies`
- 用 `POST /v1/pilot` 推下一輪
- 用 `GET /v1/hold/walk` 看關係鏈
- 用 `GET /v1/audits/{run_id}` 與 `POST /v1/mate/{run_id}` 看值不值得繼續

這樣的流程比較像研究工作台，不是查詢框。

## 效果對比

> ⚠️ 下面「3 組本地比較樣本」是規模較小、較早期的測試，不是 2026-07-03 的 Phase 3 18 題嚴謹對照實驗——見文件開頭的「待 owner 拍板」段落與 `experiments/salva_v2/ANALYSIS_FINDINGS.md`。

下面的對比不是理論推演，而是用本地比較腳本跑出來的路由差異。

### A. `find_leads`

直接走 Salva 時：

- route 偏向 `quick_scan`
- 目標是快速回答
- next queries 偏短、偏收斂

加上 agent 上下文 override 後：

- 可以切到 `company_research`
- next queries 會轉成更接近公司研究的形式
- 比較適合從 lead 擴展到 company profile

這表示 Salva 不是只會「查」，而是能根據意圖把任務升級到更合適的研究路徑。

### B. `find_companies`

直接與 agent-guided 兩邊通常都會落在 `company_research`，但 agent 版的 next queries 會更貼近新的上下文。

這說明：

- route 可能不變
- 但 query family 會變
- 這仍然會影響後續檢索品質

### C. `find_market_activity`

這類任務通常會走更深的路徑：

- `deep_investigation`
- 或後續落到 `platform_integrator`

這時 Salva 的價值不在單次 query，而在：

- 先建立信號
- 再用 pilot 產生下一輪
- 再用 audit / mate 看結果是否值得擴大

### D. 本地量化觀察

在 3 組本地比較樣本裡：

- `next_queries` 的內容在 `3/3` 組都改變了
- `route / profile` 明顯切換發生在 `1/3` 組
- 深度任務會優先落到 `deep_investigation` 或 `platform_integrator`

這個差異的重點不是「多找幾條」，而是「把下一輪變得更像研究，而不是只像搜尋」。

## 為什麼比直接搜尋更有效

- 直接搜尋只給結果，Salva 會給路徑
- 直接搜尋沒有記憶，Salva 有 query-family memory
- 直接搜尋沒有審計，Salva 有 audit / telemetry / evidence
- 直接搜尋沒有超圖，Salva 可以把 run 變成可 walk 的研究結構
- 直接搜尋沒有 tenant 控制，Salva 可以進團隊場景
- 直接搜尋沒有 route catalog，Salva 可以把 intent 對映成可解釋流程
- 直接搜尋不能根據品質自動擴並發，Salva 可以在信號弱時打開更多 provider

## 適用場景

- lead discovery
- company research
- market activity scan
- partnership signals
- event discovery
- internal research ops
- agent workflow orchestration
- 可審計的研究管線

## 不適合的場景

- 你只需要一個非常短的即時答案
- 你不需要 evidence、telemetry、route、memory
- 你不想管理任何結構化 intent

這些情況直接搜尋工具更省事。

## 和其他工具的對比

| 類型 | 它擅長什麼 | 它缺什麼 | Salva 補了什麼 |
|---|---|---|---|
| Google 手動搜尋 | 網頁廣、品牌熟、免費可用 | 要人自己判斷路徑、去重、記錄 | route、memory、evidence、audit、tenant 邊界 |
| Google Programmable Search / Custom Search API | 程式化取結果 | 仍是單輪檢索，需要自己做研究流程 | multi-round、pilot、hold、memory |
| Perplexity 類搜尋 API | 會把結果整理成可讀回答 | 研究脈絡和可重用路由較弱 | route catalog、graph walk、query-family memory |
| Tavily 類 LLM 搜尋 API | 對 agent 友好、結果清洗好 | 仍偏單次搜尋與摘要 | 超圖、審計、深度模式、可觀測性 |
| Exa 類語義搜尋 API | 語義 / 相似性搜尋強 | 研究管線和後續沉澱較少 | multi-round pipeline、memory、evidence chain |
| 手工 raw research | 彈性最大 | 最慢、最容易漏、最難複用 | 把人類研究流程固化成系統 |

如果你只想查一次，別的工具已經夠了。  
如果你要的是「越查越準、越查越像研究、越查越能交付」，Salva 才會開始有明顯優勢。

這個對比是依照公開官方文件做的：Exa、Tavily、Perplexity、Google Programmable Search。正式契約仍以各自產品文件與本 repo 的 `docs/spec/` 為準。

## 一個完整調研的推薦流程

1. 先用 `GET /v1/routes` 看該走哪條路
2. 用 `POST /v1/discover` 或 `POST /v1/jobs` 跑第一輪
3. 用 `POST /v1/pilot` 產生下一輪建議
4. 用 `GET /v1/audits/{run_id}` / `POST /v1/mate/{run_id}` 評估效果
5. 如果同類查詢反覆出現，讓 query-family memory 累積信號

這樣做的結果不是「一次查得多」，而是「越查越準」。

## 你可以怎麼向別人介紹它

你可以把 Salva 簡化成一句話：

> Salva 把搜尋變成研究系統，把結果變成可重用的路由、記憶和超圖。

再直白一點：

> 它不是幫你多查一點，它是幫你少走冤枉路，並且把每次研究都變成下次的起點。

## 入口文件

- `README.md`
- `README.zh.md`
- `docs/README.md`
- `docs/spec/README.md`
