---
name: HG-00
description: Obsidian Vault 完整索引與架構分析 — Ryan 系統現狀診斷
tags: [vault-index, architecture, diagnosis, hypergraph-memory, openclaw, BD-pipeline]
created: 2026-04-18
---

# HG-00：Obsidian Vault 完整索引與架構分析

**Ryan 超圖記憶系統現狀診斷**
**日期：2026-04-18**
**目標：建立 vault 索引 → 識別缺口 → 規劃整合路徑**

---

## 1. Vault 整體檔案地圖

```
workspace/
├── research/              ← 調研文檔（HG-01~07 + 0321 系列）
│   ├── HG-01~07           ← 超圖記憶系統研究（HG-01~06 完成，HG-07 2026-04-19）
│   ├── 2026-03-21/        ← BD Pipeline 調研（21 Topic，半成品）
│   └── 2026-03-21-Complete.md  ← 0321 調研總結
│
├── 指導文件/              ← 系統設計的最高指導（核心！）
│   ├── SALVA_V2_ARCHITECTURE_REVIEW.md  ← Salva v2 目標架構
│   ├── 自動化 BD Leads 系統：7 流程架構規格.md  ← BD 系統骨幹
│   ├── Piper - empower the low-Bs.md   ← 意圖理解層
│   ├── Handy-Slowly make agents smarter.md  ← 執行反饋層
│   ├── Memory optmization thoughts.md   ← 四層記憶架構
│   ├── Salva_OSINT_Enrichment_Master_Plan.md  ← OSINT 整合計畫
│   ├── Waker - Event-Driven Agent Wake System.md  ← 事件喚醒
│   └── Archive/              ← 歸檔舊版本
│
├── Momotoy/               ← 客戶項目文件（PRD/DRD）
├── bd/                    ← BD 外展系統
│   ├── agent/              ← Agent 每日產出（leads/summary）
│   ├── outreach-drafts/     ← 外展文案草稿
│   ├── outreach-batches/    ← 批次外展記錄
│   └── templates/          ← 外展模板（9+ 種 variant）
│
├── ryan/                  ← Ryan 私人文件
│   ├── job-search-*.md     ← 求職計畫與進度
│   └── job-research-iteration.md  ← 求職迭代研究
│
├── memory/                ← 系統記憶文件
├── plans/                 ← 計劃文件
├── tasks/                 ← 任務追蹤
├── logs/                  ← 日誌
├── 財務整理/              ← 財務記錄
├── 开会记录.md             ← 會議記錄
└── 終於和gpt一起在claw上合作了.md  ← 41KB 核心對話歷史
```

**總計：~100 個 .md 檔案**

---

## 2. 核心系統設計主線（三條）

### 主線 A：BD 自增強操作系統（BD Agent OS）
> 把 OpenClaw 變成會自己找線索、整理記憶、優化流程、逐步推進 BD 的 agent operating system。

**骨幹文件：** `自動化 BD Leads 系統：7 流程架構規格.md`

```
1. 目標定義 → 2. 關鍵詞生成 → 3. 搜索採集 → 4. 抓取提取
→ 5. 清洗去重打分 → 6. 記憶沉澱 → 7. 輸出跟進
     ↺ ←─────── 迴圈反饋 ───────↺
```

**7 Flow 現狀評估：**
- Flow 1–3（目標/關鍵詞/搜索）：Salva v2 設計覆蓋
- Flow 4–5（抓取/OSINT/打分）：OSINT Master Plan 覆蓋
- Flow 6（記憶沉澱）：**缺口最大** — LanceDB 幾乎是空的
- Flow 7（輸出跟進）：模板系統完整（9+ outreach variants）

### 主線 B：Salva — Discovery Intelligence Layer
> 把搜索從一次性 query，變成可沉澱、可強化、可回寫的 intelligence loop。

**四個模式對應四種搜索策略：**
| 模式 | 策略 |
|------|------|
| Dive | 精準 operator 搜索 |
| Anchor | 關鍵詞圖 + 多輪擴展 |
| Pirate | 非常規抓取 |
| Radar | 市場與輿情雷達 |

**核心問題（Salva V2 Review 指出）：**
1. 查詢仍是靜態字串，非結構化對象
2. 缺少搜索遙測（成功率/噪音率/去重率）
3. Keyword Graph 從未真正實現

### 主線 C：四層記憶架構（Memory Optimization Thoughts）
> 這是整個系統的記憶核心，與 HG 系列研究高度吻合。

```
┌─────────────────────────────────────┐
│  LLM Context                        │
│  = STATE + CONTEXT_BRIEF            │
│    + retrieved memory + recent actions│
└─────────────────────────────────────┘
         ↑ 不要塞完整對話歷史

四層：
L1 Working Memory   → STATE.json / PLAN.md / CONTEXT_BRIEF.md
L2 Episodic Memory   → memory/raw/ / memory/summaries/
L3 Semantic Memory   → LanceDB vector store
L4 Global Facts     → Obsidian vault（人讀真實來源）
```

**現狀問題：**
- LanceDB 總Count: 0（有效長期記憶沉澱幾乎沒有形成）
- 真正承擔記憶功能的是：MEMORY.md + vault 文檔 + prompt 文本

---

## 3. 各系統組件狀態評估

### 3.1 Piper（意圖理解層）
**職責：** 模糊輸入 → 結構化任務表示
**位置：** 用戶輸入 → 主模型之間
**模組：** Input Analyzer / Intent Analyzer / Semantic Expansion Engine / Task Constructor / Feedback Loop
**狀態：** 設計完整，實現未知（文檔有代碼結構但未驗證）

### 3.2 Handy（執行反饋層）
**職責：** skill 表現評估 / 打分 / 修正建議 / 排序更新
**位置：** 執行之後，進化層之前
**模組：** Execution Logger / Feedback Analyzer / Performance Evaluator / Patch Generator / Ranking Updater
**狀態：** 設計完整，實現未知

### 3.3 Salva（搜索智能層）
**職責：** 多模式 OSINT 搜索 + 關鍵詞圖擴展
**模式：** Dive / Anchor / Pirate / Radar
**現狀：** Skill 封裝完整，但 runtime 沒有真正跑起來

### 3.4 Waker（事件喚醒系統）
**職責：** Event-Driven Agent Wake System
**狀態：** 設計存在，實現未知

### 3.5 OSINT 整合計畫
**職責：** theHarvester / Amass / Recon-ng / SpiderFoot / Maltego
**Phase 1：** CLI 腳本嵌入 Pipeline
**Phase 2：** Plugin 化（OpenClaw API Agent）
**Phase 3：** Platform API（企業級情報圖譜）
**現狀：** Phase 1 待開發

### 3.6 BD Outreach System
**模板數：** 9+ variants（standard / brand-collab / distributor / retailer / follow-up / marketplace-platform 等）
**外展語言：** 中英混雜，多地區對應
**狀態：** 模板完整，但與 Salva 無串接

---

## 4. HG 系列研究 vs 指導文件對照

| 維度 | HG 系列研究 | 指導文件 |
|------|-----------|---------|
| **理論基礎** | HG-01/02（論文+關鍵詞）| — |
| **完整技術調研** | HG-03（Hypergraph-DB + Schema 設計）| — |
| **競品分析** | HG-04（Mem0/Letta/OMEGA/A-Mem）| — |
| **源碼分析** | HG-05（GenericAgent/Evolver）| — |
| **系統架構** | HG-0A（三套記憶系統對比）| BD 7-flow + 四層記憶 + Piper + Handy |
| **記憶實現** | Hypergraph-DB（實測可行）| 四層記憶（LanceDB 仍是 0）|

**關鍵發現：**
- HG 系列研究填補了「理論 + 國外競品調研」的空白
- 指導文件定義了「Ryan 自己系統的設計意圖」
- **兩者之間缺少橋接**：研究結論沒有被轉換為可執行步驟寫入系統

---

## 5. 審計結論：缺口識別

### 5.1 記憶系統缺口（最大問題）

```
目標：Hypergraph-DB + Jina + Obsidian vault
現狀：HG-03 設計完整，但從未真正寫入 Hypergraph-DB
      LanceDB 總Count: 0
      真正的記憶仍是 .md 文件
```

### 5.2 整合缺口

```
HG 研究結論 → 沒有落實到系統
Salva/Piper/Handy → 設計存在但沒有驗證是否在跑
BD 7-flow → 有架構但流程6（記憶沉澱）最弱
```

### 5.3 0321 調研問題

| 文件 | 問題 |
|------|------|
| A1–F3（13份）| 模板完整但核心發現幾乎全空 |
| X16–X21（6份）| 幾乎是廢文（標題重複/0 sources/質量3分）|
| A2（Hybrid Search）| 標題好但關鍵詞詭異（「xu6z0zRQ」出現在術語中）|

### 5.4 HG-04 幻覺問題（已確認）

```
錯覺：有 100+ 篇論文支撐
實際：18 篇精選參考文獻
影響：結論方向仍然正確（超圖/HGNN/記憶架構）
      但數字需要修正
```

---

## 6. Ryan 提出的整合流程分析

Ryan 的完整流程：
```
① 審計 vault（逐篇查讀）
② 建立索引
③ 整合資料
④ 提出多個解決方案
⑤ 組合最適方案
⑥ 結晶固化封裝為 skill/pipeline
⑦ 寫入 prompt/cron/daemon
```

### 6.1 這個流程是否合理？

**完全合理，且是正確順序。** 理由：

```
① 審計 vault
  → 避免重蹈覆轍（避免 HG-04 幻覺式總結）
  → 建立客觀事實庫（剛剛完成的步驟）

② 建立索引
  → 讓每次引用都有精確出處
  → 消滅「感覺上有」的幻覺

③ 整合資料（這個步驟最複雜）
  → HG 系列（外源研究）vs 指導文件（內源設計）需要橋接
  → 需要去除重複、識別矛盾、標記層次

④ 提出多個解決方案
  → 目前缺口只有一個：記憶沉澱沒落實
  → 但可以從三個角度提出方案（見 6.2）

⑤ 組合最適方案
  → 當前最優：Hypergraph-DB + 四層記憶 + BD 7-flow 整合

⑥ 結晶固化封裝
  → 變成 Herms skill（bd-piper 等已有類似實踐）

⑦ 寫入 prompt/cron/daemon
  → 這是最終目標：讓系統自動運行
```

### 6.2 三個解決方案方向

**方案 A：最小可行（MVP，1–2週）**
```
只做一件事：把當前 vault 裡的決策寫入 Hypergraph-DB
- 讀取 HG-03 的 Schema 設計
- 手工建立前 10 個頂點/超邊（Ryan/Emily/關鍵項目）
- 用 Jina embedding 驗證檢索
- 不改任何現有流程
```

**方案 B：整合方案（1個月）**
```
把 Hypergraph-DB 接入 BD 7-flow Flow 6
- Flow 6（記憶沉澱）現在是缺口
- 用 Hypergraph-DB 替代「寫入 .md」
- Salva v2 的 Keyword Graph 存入超邊
- Piper/Handy 產出寫入 episodic memory
```

**方案 C：完整方案（長期）**
```
把 Hypergraph-DB 當作記憶核心
- 廢除 LanceDB（因為它是黑盒子）
- Piper = Hypergraph攝入層
- Handy = Hypergraph 反饋層
- Salva = Hypergraph 擴展層
- 記憶永遠雙寫：Hypergraph-DB + Obsidian vault
```

### 6.3 我的判斷：應該從方案 A 切入

理由：
1. **風險最低**：不改任何現有流程，只驗證核心假設
2. **驗證核心**：Hypergraph-DB 到底能不能表達 Ryan 的實際關係
3. **快速反饋**：1–2天就能知道 Schema 是否合理
4. **為 B/C 墊底**：方案 A 的產出直接是方案 B 的輸入

---

## 7. 待填補的具體缺口清單

| 缺口 | 優先級 | 對應文件 | 備註 |
|------|-------|---------|------|
| HG-04 數字幻覺（18篇≠100+）| 高 | HG-04 | 需修正陳述 |
| BD 7-flow Flow 6 記憶沉澱 | 高 | 自動化 BD Leads 系統 | 最關鍵缺口 |
| LanceDB 總Count: 0 | 高 | memory-lancedb-pro | 真正記憶承載是.md |
| Hypergraph-DB 從未真正寫入 | 高 | HG-03 Schema | 設計有但未実行 |
| 0321 X16-X21 廢文 | 中 | research/2026-03-21/ | 可刪除或重建 |
| Salva v2 結構化 Query 對象 | 中 | SALVA_V2_ARCHITECTURE_REVIEW | 現仍是靜態字串 |
| Keyword Graph 從未實現 | 中 | Salva 指導文件 | 設計有但未実装 |
| Piper/Handy 沒有驗證 | 低 | Piper/Handy 文檔 | 設計好但位置靠後 |
| OSINT Phase 2/3 未啟動 | 低 | Salva_OSINT_Enrichment_Master_Plan | Phase 1 也没做 |
| Claw_coop 41KB 沒有結構化 | 低 | 終於和gpt一起在claw上合作了.md | 是對話歷史非設計文檔 |

---

## 8. Anna's Archive 用於論文獲取

Anna's Archive 是全球最大影子圖書館元搜尋引擎：
- 聚合 Z-Library + LibGen + Sci-Hub
- 支援 DOI/arXiv ID 直接檢索
- Agent-friendly（可程式化調用）

**可用於：**
- 獲取 HG-04 精選的 18 篇論文全文
- 補充 HG-01/02 中無法直接訪問的 arXiv 論文
- 對比國外記憶系統的實際代碼/論文

**用法：**
1. 到 annas-archive.org 搜索論文名或 arXiv ID
2. 下載 PDF
3. 用 web_extract 直接解析 PDF URL

---

## 9. 下一步行動（Ryan 確認後執行）

```
Step 1（立即）：修正 HG-04 數字（18篇代替100+）
Step 2（1天）：方案 A — Hypergraph-DB MVP
              - 建立前10個頂點（Ryan/Emily/核心項目）
              - 驗證 Schema 是否work
Step 3（3天）：把 BD 7-flow Flow 6接入 Hypergraph-DB
Step 4（1週）：整合 Salva v2 的 Keyword Graph 存入超邊
Step 5（持續）：根據反饋迭代調整 Schema
```

---

## 附錄：0321 文件質量評估

| 文件 | 大小 | 質量 | 建議 |
|------|------|------|------|
| A1 Elasticsearch vs LanceDB | 9KB | 中 | 框架有，內容空洞 |
| A2 Hybrid Search | 12KB | 中 | 關鍵詞有問題（干擾）|
| A3 SearXNG Deployment | 6KB | 中 | 框架有，內容空洞 |
| B1 Keyword Research | 14KB | 中 | 框架有，內容空洞 |
| B2 AEO LLM Optimization | 11KB | 中 | 框架有，內容空洞 |
| C1 OpenClaw Skill Spec | 10KB | 高 | 實際有用 |
| C2 Agent Skill Frameworks | 6KB | 中 | 框架有，內容空洞 |
| D1 OpenClaw Plugin Arch | 10KB | 高 | 實際有用 |
| D2 VSCode Plugin Reference | 12KB | 中 | 參考價值 |
| E1 Embedding Models | 11KB | 高 | 實際有用 |
| E2 Rerank Models | 10KB | 高 | 實際有用 |
| E3 Graph Based Retrieval | 6KB | 高 | 與 HG-03 呼應 |
| F1 RAG Frameworks | 10KB | 中 | 框架有，內容空洞 |
| F2 Agent Patterns | 9KB | 中 | 框架有，內容空洞 |
| F3 Reference Projects | 7KB | 中 | 框架有，內容空洞 |
| X16–X21 | 各0KB | ❌ | 刪除候選 |
