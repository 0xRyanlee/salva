# Salva OSINT Enrichment Master Plan

> **Version**: 1.0  
> **Purpose**: Define the integration strategy for professional OSINT tools (SpiderFoot, Maltego, theHarvester, Amass, Recon-ng) within the Salva Automated BD Leads Pipeline (Phase 4 & 5).  
> **Objective**: Enrich raw company domains into high-fidelity BD profiles (emails, key personnel, technical infrastructure, social footprints) before Agent scoring.

---

## 1. 核心定位與架構 (Positioning & Architecture)

在現有的「自動化 BD Leads 系統：7 流程架構」中，OSINT  Enrichment 位於 **4. 抓取與提取** 和 **5. 清洗去重打分** 之間。

- 原有流程：SearXNG 抓取 -> 清洗 -> 儲存。
- **全新 OSINT 賦能流程**：SearXNG 獲取原始 URL/Domain -> **OSINT Pipeline 擴展情報 (Emails, Subdomains, Social, Tech Stack)** -> 結構化交給 Agent 打分 -> LanceDB 儲存。

---

## 2. 五大 OSINT 工具詳盡分析與職責劃分

為了避免工具重疊，我們為每個 OSINT 工具指派了最精確的 BD (Business Development) 任務：

### 1. theHarvester (高效率基礎爬蟲)
- **BD 職責**：**快速 Email 與員工名單收集**。
- **技術特性**：羽量級、CLI 驅動。利用搜尋引擎、PGP 伺服器、SHODAN 等被動來源快速找出目標網域的 Emails、子域名與公開 IP。
- **使用時機**：獲取公司網域後的第一道擴展防線。

### 2. Amass (深度基礎設施掃描)
- **BD 職責**：**評估經銷商規模與技術堆疊**。
- **技術特性**：由 OWASP 維護，最強的 DNS 列舉與攻擊面映射工具。
- **使用時機**：當需要判斷對方是「單人小賣家」還是「擁有龐大 IT 系統的跨國大型通路商」時，透過 Amass 掃描其子網域範圍即可精準推測。

### 3. Recon-ng (模組化 Web 情報聚合)
- **BD 職責**：**客製化 API 聚合器**。
- **技術特性**：類似 Metasploit 的框架，但專注於 Web Recon。可動態掛載各類模組 (如 Hunter.io, LinkedIn, X API)。
- **使用時機**：用於需要調用第三方 API 互相交叉比對的精細調查。

### 4. SpiderFoot (自動化開源情報中樞)
- **BD 職責**：**全方位公司數位足跡建立**。
- **技術特性**：強大的自動化 OSINT 平台，內建 200+ 模組。支援 API Server 模式。
- **使用時機**：針對「高價值目標 (High-Value Targets)」，調用 SpiderFoot API 進行 360 度掃描，找出關聯企業、潛在黑歷史或極深度的聯絡管道。

### 5. Maltego (視覺化關聯分析)
- **BD 職責**：**複雜集團架構與關鍵決策者圖譜破解**。
- **技術特性**：圖形化節點分析，透過 Transforms 關聯各種實體 (Entity)。
- **使用時機**：由人類（或頂級 Agent）在 UI 層面分析超級經銷商的母子公司結構、董事會人脈關聯時使用。不適合每秒高頻調用。

---

## 3. 系統整合平台化：三階段實裝計畫 (Phased Rollout)

OSINT 的整合分階段推進，對應 OpenClaw 的架構：

### Phase 1: Skills 層疊 (Terminal/Python Execution)
**目標**：最小成本嵌入現有 Pipeline。
- **實作**：將 `theHarvester` 與 `Amass` 包裝成 Python CLI 腳本（類似 `salva-pipeline.sh` 中的一環）。
- **流程**：Orchestrator 拿到 Domain 後，在背景直接對目標執行 `python3 scripts/run_harvester.py -d domain.com`，並將撈到的 Email 寫入 LanceDB，供 Agent 評分參考。不消耗 LLM Token。

### Phase 2: Plugins 插件化 (OpenClaw API Agent 賦能)
**目標**：賦予 Agent 針對特定目標展開「主動調查」的能力。
- **實作**：將 `Recon-ng` 和 `SpiderFoot API` 封裝進 OpenClaw Plugin (例如 `osint-core`)。
- **流程**：在對話中，Agent 發現某個關鍵字很可疑，主動調用工具 `call_osint_recon({ domain: "target.com" })`。這個工具會代理調用 SpiderFoot API 掃描，並以 JSON 結構回傳結果給 Agent 分析。

### Phase 3: Platform API (Data Plane 平台化)
**目標**：建立企業級情資圖譜資料庫。
- **實作**：架設獨立的 SpiderFoot/Maltego Server。原有的 `salva_search` 獲取線索後，非同步將任務丟入到情報伺服器。
- **流程**：情報平台 (Data Plane) 日夜不停地清洗資料，並定時透過 Webhook 將高權重的實體 (Entity) 同步回 LanceDB 知識庫 (`memory/index`)。Agent 完全退居「決策者」，只需調閱已準備好的極度豐富的 BD 檔案。

---

## 4. 舊文件歸檔說明 (Deprecation Notice)
為了避免系統冗雜與架構混淆，知識庫已進行以下清理：
1. `oldbddata` 目錄：屬於極早期手動架構，已歸檔/刪除。
2.舊版 `Salva Skill.md` (充滿破碎 OSINT 概念的草稿)：已將核心精神（如 Pirate 模式、TheHarvester 點子）吸收進本文件中，原檔案已移除。
3.保留 `進階搜尋運算符庫.md`：作為底層檢索邏輯的真理。
4.保留 `自動化 BD Leads 系統：7 流程架構規格.md`：作為高階骨幹流程。

> **下一步行動 (Action Item)**：開發 `Phase 1` 所需的 `salva_enrichment.py` 接頭，將 theHarvester 與 Amass 正式掛載到 `salva-qualifications.py` 之前。
