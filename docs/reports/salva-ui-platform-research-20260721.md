# Salva UI 平台研究：CRM / GA4 / 經營管理後臺風格介面

> 日期：2026-07-21
> 對應 mindset 板任務：`salva-ui-platform-research-crm-style`
> 定位：把 `CLAUDE.md`「GUI Fork（salva-ui）」段落具體化，不是另開平行方向——沿用其「獨立 repo、對接穩定 REST/MCP contract、不併入本 repo」的前提。

## 1. 三種參考型態的核心 UX 模式

**CRM 類（HubSpot / Attio）**：HubSpot 的核心是 deal pipeline 看板——每個 stage 一欄，deal 卡片可拖拉，record 頁用「cards」組裝任意來源的關聯資訊（activity、association stage tracker）。Attio 更貼近本案：捨棄「system of record」語彙，改用 **Objects / Records / Attributes** 三層模型，任何實體都是自訂 object，record 頁有 **Shared Timeline** 把 email、note、call、stage 變更全部按時間軸聚合成單一視圖，且支援 list/board/calendar/timeline 多種 view 自由切換而不改變底層 schema。

**GA4 類**：三種機制分工——**Reports**（預聚合、24-48h 延遲、給例行監看）、**Explorations**（ad-hoc 自由分析，含 funnel/path/free-form 模板）、**Library**（依角色組織 Collection、決定不同角色預設看到哪組報表）。最佳實踐是拆成 3-4 個聚焦儀表板而非一個大而全視圖，管理層看 5-card 摘要，分析者看細節表。

**經營管理後臺類（admin/ops console）**：以**資料表格**為核心互動面——多欄排序、進階篩選、inline edit、bulk action（勾選多筆→浮出工具列做批次動作）、可儲存的 view preset；狀態轉換用色碼徽章 + SLA 逾時視覺升級提示；RBAC 決定不同角色看到的欄位與可執行動作。

## 2. 對照 Salva 能力的落地建議

Salva 的產出是「entity + relation + evidence chain + telemetry」，且底層是 **n-ary hypergraph**（`hold/schema.py` 的 `HoldHyperedgeRecord`：members 帶 role/weight/evidence_ids，不是簡單的二元關聯）。這比 CRM 的「聯絡人-公司-交易」三元關係更複雜，直接套用 HubSpot 式固定欄位卡片會失真。建議：

- **檢索任務視覺化 → 混合 CRM pipeline + GA4 Report 列表**：一次 discover/job run 當作一張「pipeline card」，state（queued/running/done/failed）用色碼徽章，這是 admin console 的狀態轉換模式；但列表層級（哪些 run 值得看）用 GA4 式 Report/Exploration 二分——「Runs 總覽」是預聚合報表，「單一 run 深潛」是自由探索視圖。
- **結果沉澱表格 → Attio 式 Object/Record，而非 Airtable 完全自由表**：canonical schema 已固定（entity_type/relation_type 有伺服器端 schema，見 `/v1/hold/schema/entities`），UI 不該讓使用者亂加欄位破壞契約，但**可以**讓使用者自訂 view（篩選、排序、可見欄位）疊在固定 schema 上——這正是 Attio「object 固定、view 自由」的分寸。record 詳情頁採 Shared Timeline 模式：把 evidence chain 按時間排列，取代 CRM 的 email/call 記錄。
- **檢索流程工作流編排 → 這塊目前 Salva 後端沒有對應概念**，`core/controller.py` 只管單次 run 內的多輪策略，沒有「使用者自訂串接多個 discover 步驟」的持久化物件。若要做 Zapier/n8n 式 visual pipeline builder，是這次研究裡**唯一需要新後端能力**的部分（見第 5 節）。MVP 階段建議先不做完整 node-canvas 編輯器，用「多步驟表單精靈」（admin console 常見模式）替代，把 node graph builder 留到 v2。

## 3. MVP 範圍草案

**第一版做**：① Run 總覽列表（GA4 Report 式，含狀態徽章、篩選、分頁）② 單一 run 詳情（entity/relation 表格 + evidence timeline，Attio 式 record 頁）③ 建立新 discover/job 的表單（對應現有 preset/route，非 visual builder）④ Audit/Pilot 面板（把既有 `/v1/audits`、`/v1/pilot` 資料視覺化，這是 Salva 獨有、CRM/GA4 都沒有的差異化面）。

**延後到 v2+**：visual pipeline/workflow builder（node canvas）、自訂 view 的伺服器端持久化、多租戶 RBAC、跨 run 的 hypergraph 探索式圖視覺化（`/v1/hold/walk` 已有資料但圖形化 UI 成本高）。

## 4. 技術棧初步建議

沿用 repo 慣例走 **Tauri**（跨 Sparkie/Mindset/Cuckoo 一致）沒有問題，但視覺語言**不建議套用 `glass-dark-tool-design`**——那套是給 dev terminal / CLI GUI 的暗色玻璃質感，設計前提是「稀疏、高對比、terminal 氛圍」。CRM/GA4/admin 後臺的共通點是**資料密集、長時間盯表格**，業界慣例（HubSpot、Attio、多數 admin dashboard）預設走**亮色、高可讀性、密度可調**的資料表格風格，暗色只作為次要選項。建議另立一套設計語言（可延續 design-program 流程單獨跑一輪 shotgun），不強套現有暗色基準。

## 5. 與現有 REST/MCP contract 的整合點

現有 API 已相當完整（50+ endpoint），UI 直接消費即可，不需大改：`/v1/discover`、`/v1/jobs`(+`/stream` SSE 可做即時進度)、`/v1/runs`、`/v1/evidence`、`/v1/evidence/chains`、`/v1/hyperedges`、`/v1/hold/views`、`/v1/hold/walk`、`/v1/audits/{run_id}`、`/v1/pilot`、`/v1/presets`、`/v1/routes`、`/v1/usage`、`/v1/quota` 都可直接對映到上述 MVP 畫面。**需要新增的端點只有兩類**：① 使用者自訂 view 的持久化（篩選/排序/可見欄位 preset，目前 `/v1/hold/views` 是伺服器預定義投影，不是使用者可寫入的物件）② 若要做工作流編排，需要一個新的「saved workflow」資源（多個 discover/job 步驟 + 條件跳轉的定義），目前 controller 層沒有這個概念，需先在後端立案再談 UI。這兩項都應該先過 owner 拍板再排入後端 backlog，不在這次 UI 研究範圍內動手實作。
