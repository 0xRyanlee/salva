---
name: HG-06
description: "Step ③ 整合文件：外源研究(HG-01~05)與內源設計(指導文件)的橋接，統一 Schema、記憶層次、數據庫分工、Flow 6 具體化
tags: [integration, schema, memory-layer, hypergraph, architecture, BD-pipeline, Flow-6]
created: 2026-04-18
sources: HG-01~05 + 指導文件(SALVA_V2/MEM_OPT/7-FLOW/PIPER/HANDY/OSINT) + Claw_coop 41KB
---

# HG-06：整合架構設計——外源研究 × 內源設計橋接方案

**Ryan 超圖記憶系統 Step ③**
**日期：2026-04-18**
**目的：消除五大設計張力，提出統一路線**

---

## 1. 五大設計張力與橋接結論

### 張力 1：Hypergraph-DB vs LanceDB

| 文件 | 立場 |
|------|------|
| HG-01~05, HG-0A | Hypergraph-DB（n-ary 超邊，原生 Python）|
| MEM_OPT, 7-FLOW, OSINT | LanceDB（向量記憶）|
| Claw_coop 41KB | **LanceDB 總Count: 0，沒跑起來** |

**橋接結論：分層分工**

```
記憶查詢流：
  Jina embedding（oMLX）
    ↓
  向量相似度預篩選（top-k）
    ↓
  Hypergraph-DB（n-ary 結構擴展）
    ↓
  Obsidian vault（人讀最終真相）

Hypergraph-DB  = 結構關係引擎（主要 DB，Ryan 的選定）
LanceDB         = 向量加速層（過渡方案，可選）
                  → 最終目標：oMLX Jina 直接替代 LanceDB
```

**理由：** LanceDB 是 0 的原因不是它不好，而是從未被真正接入。HG 系列已完整測試 Hypergraph-DB，Python 原生，Ryan 的工具鏈最順。兩者功能重疊，保留一個更穩。

---

### 張力 2：三套實體類型 → 統一 Vertex Schema

| 來源 | 類型 |
|------|------|
| HG-03 | note / person / topic / skill / session |
| MEM_OPT | lesson / decision / failure_summary / repo_summary / research_note / rule_reference |
| SALVA_V2 | company_name / domain / market / industry / role / qualification_id |
| 7-FLOW | lead profile（industry/region/role/company_type/score）|

**橋接結論：統一 Vertex Schema（整合版）**

```
┌──────────────────────────────────────────────────────────────┐
│  Vertex Type: person                                         │
│  Examples: Ryan, Emily, 某個 Lead 公司                       │
│  Attributes: name, role, description, embedding_id           │
├──────────────────────────────────────────────────────────────┤
│  Vertex Type: topic                                          │
│  Examples: hypergraph, BD-leads, ArtToy, job-search          │
│  Attributes: name, category, tags[], embedding_id             │
├──────────────────────────────────────────────────────────────┤
│  Vertex Type: note                                           │
│  Examples: HG-03, outreach-template, PRD                      │
│  Attributes: path, title, tags[], content_hash, embedding_id │
├──────────────────────────────────────────────────────────────┤
│  Vertex Type: skill                                          │
│  Examples: salva-dive, piper-意图分析, handy-反馈评估        │
│  Attributes: name, category, type, description                │
├──────────────────────────────────────────────────────────────┤
│  Vertex Type: session                                         │
│  Examples: 2026-04-18對話, job-interview-2026-04-14          │
│  Attributes: id, timestamp, summary, type                     │
├──────────────────────────────────────────────────────────────┤
│  Vertex Type: lead           ← 【新增，來自 SALVA_V2】      │
│  Examples: ToyDistributor-Japan-2026Q2, EuropaPlushCo        │
│  Attributes: company_name, domain, market, industry,          │
│              role, qualification_id, contact_status,          │
│              confidence_score, source_url, created_at        │
├──────────────────────────────────────────────────────────────┤
│  Vertex Type: semantic_entry  ← 【新增，來自 MEM_OPT】       │
│  Examples: lesson:hypergraph-complexity, decision:v1.0      │
│  Attributes: type, content, tags[], confidence, created_at   │
│  Types: lesson / decision / failure_summary / repo_summary   │
│         research_note / rule_reference                        │
└──────────────────────────────────────────────────────────────┘
```

---

### 張力 3：記憶層次 → 統一 Hypergraph Memory Layers

| 來源 | 層次 |
|------|------|
| MEM_OPT | Working / Episodic / Semantic / Global Facts |
| GenericAgent | L0 Meta Rules / L1 Insight / L2 Facts / L3 Skills / L4 Sessions |
| HG-0A | Hermes偏好 / Obsidian / BDDB |

**橋接結論：統一六層（覆蓋所有來源）**

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 0 — Meta Rules（不可覆蓋的行為約束）                 │
│  Storage: Hypergraph-DB vertex (type: meta_rule)            │
│  Content: "不執行刪除操作"、"所有寫入需要雙寫 Obsidian"   │
│  Access: 只讀，從不通過記憶檢索                             │
├─────────────────────────────────────────────────────────────┤
│  Layer 1 — Working Memory（當前任務狀態）                    │
│  Storage: STATE.json / PLAN.md（文件系統）                   │
│  Content: 當前任務目標、已選技能、上下文摘要                │
│  Access: 每次對話都注入，不走 Hypergraph-DB                  │
├─────────────────────────────────────────────────────────────┤
│  Layer 2 — Episodic Memory（執行的足跡）                    │
│  Storage: Hypergraph-DB vertex (type: session)              │
│  + memory/raw/（原始對話日誌）                              │
│  Content: tool calls、執行步驟、失敗蹤跡、任務摘要          │
│  Access: 調試/回放用，不注入上下文                          │
├─────────────────────────────────────────────────────────────┤
│  Layer 3 — Semantic Memory（Hypergraph-DB 核心）             │
│  Storage: Hypergraph-DB（超邊 + topic/person/skill vertices）│
│  Content: 所有結構化關係（person_context / topic_cluster /   │
│           skill_dependency / keyword_graph / lead_profile）  │
│  Access: 主要記憶檢索入口（向量預篩 → 結構擴展）            │
├─────────────────────────────────────────────────────────────┤
│  Layer 4 — Obsidian Vault（人讀最終真相）                    │
│  Storage: Obsidian .md files（iCloud 同步）                  │
│  Content: 所有研究文檔、工作記錄、PRD/DRD、模板             │
│  Access: 人類直接讀寫，Hypergraph-DB 鏡像同步               │
├─────────────────────────────────────────────────────────────┤
│  Layer 5 — External DB（專案數據，Hypergraph-DB外部）        │
│  Storage: BDDB SQLite / 104 API / LinkedIn 等               │
│  Content: 非 Ryan 私人記憶的外部數據                        │
│  Access: 作為 Hypergraph-DB 的 leaf 節點，不寫入 HG         │
└─────────────────────────────────────────────────────────────┘
```

---

### 張力 4：Obsidian 角色（已有共識）

**共識：** Obsidian = 人可讀最終真相庫，雙寫策略

```
當 Hypergraph-DB 建立/更新任何頂點/超邊時：
  → 同步寫入 Obsidian 對應 note（或更新現有 note 的 YAML frontmatter）

當 Obsidian note 有結構化更新時：
  → 同步更新 Hypergraph-DB 對應頂點

 Obsidian 的 YAML frontmatter 是 Hypergraph-DB 的「外觀」：
---
vertex_id: person:Ryan
type: person
tags: [Ryan, user, 創業者]
description: 前 Momotoy 員工，現求職中
---
```

---

### 張力 5：Keyword Graph vs Hypergraph

**橋接結論：Keyword Graph 是 Hypergraph 的一類超邊**

```
SALVA_V2 Keyword Graph Node：
  {phrase, market, role, category, weight}

→ 映射為 Hypergraph Vertex (type: topic, category: keyword)
  {"name": "plush distributor Japan",
   "category": "keyword",
   "market": "Japan",
   "role": "distributor",
   "weight": 0.85}

SALVA_V2 Keyword Graph Edge（synonym/specialization/region...）
→ 映射為 Hypergraph Hyperedge (type: keyword_relation)
  {
    "type": "keyword_relation",
    "relation": "synonym",
    "members": ["plush toy", "collectible toy", "designer toy"],
    "source": "Jina rerank"
  }
```

---

## 2. Flow 6 具體化（最大缺口填補）

**7-FLOW 原本對 Flow 6 的定義：**
> 「記憶沉澱與經驗強化」
> 「讓系統回憶過去相近市場和 lead 任務」
> **缺口：沒有給出具體的數據模型或工作流程**

### Flow 6 整合後的完整定義

```
Flow 6: 記憶沉澱與經驗強化
觸發時機：每次 Flow 5（清洗/打分）完成後
觸發時機：對話結束時
觸發時機：每日定時（cron）

┌─────────────────────────────────────────────────────────────┐
│ Step 6.1：Lead 結構化寫入 Hypergraph-DB                    │
│                                                             │
│  新 lead vertex：                                          │
│    vertex_id: lead:{company_name}:{date}                   │
│    type: lead                                              │
│    market / industry / role / confidence_score             │
│                                                             │
│  新超邊：                                                  │
│    hyperedge: topic_cluster                                │
│    members: [lead, topic:{market}, topic:{industry}]       │
│    type: lead_market_cluster                               │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 6.2：經驗萃取寫入 semantic_entry                       │
│                                                             │
│  每次 Flow 3-5 完成後，萃取：                              │
│  - lesson: 哪些關鍵詞帶來了高質量 lead                     │
│  - decision: 本次選擇了哪個市場/角色組合                    │
│  - failure_summary: 哪些查询完全無效                       │
│                                                             │
│  → 寫入 Hypergraph-DB vertex (type: semantic_entry)        │
│  → 用於後續 Flow 2 的關鍵詞權重更新                        │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 6.3：雙寫 Obsidian                                    │
│                                                             │
│  每次 Flow 6 完成後：                                      │
│  → 更新 Obsidian lead note                                 │
│    （BD/leads/{date}-{company}.md）                        │
│  → 更新 Obsidian YAML frontmatter                          │
│    （vertex_id, hypergraph_synced: true）                  │
│  → 添加 lesson 到記憶總結 note                              │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 6.4：Hop 查詢驗證（可選，未來）                       │
│                                                             │
│  基於 Jina embedding 的 hop 查詢：                         │
│  "過去在歐洲做 distributor 的 lead 有哪些？"               │
│  → 向量預篩 → Hypergraph hop 擴展 → 返回結果              │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Piper / Handy 在整合架構中的位置

```
User Input
    ↓
Piper（意圖理解層）← Layer 1 的攝入口
    ↓ 任務結構化
Layer 3 Hypergraph-DB（檢索）← Jina 預篩 → 結構擴展
    ↓
Execution（Salva / BD Pipeline / GenericAgent tools）
    ↓
Handy（執行反饋層）← Layer 2 的觸發器
    ↓ 打分 + 修正建議
Layer 3 Hypergraph-DB（寫入）← Flow 6 沉澱
    ↓
Obsidian（雙寫）
```

**Piper 職責更新：**
- 將用戶模糊輸入轉為結構化任務
- 任務意圖路由（BD Leads / 求職 / 研究 / 日常）
- 決定是否觸發 Flow 6 沉澱

**Handy 職責更新：**
- 對 skill/flow 表現打分
- 生成 Flow 6 的 `semantic_entry`（lesson / decision / failure_summary）
- 維護 Layer 3 的 hyperedge quality 權重

---

## 4. 統一技術棧

```
核心引擎：Hypergraph-DB（Python，原生超邊）
向量檢索：oMLX Jina（替代 LanceDB，最終方案）
人讀真相：Obsidian vault（雙寫目標）
圖表徵：SALVA_V2 Keyword Graph → Hypergraph hyperedge (keyword_relation)

查詢流程：
  Query → Jina embedding (oMLX)
    → 向量 top-k → Hypergraph-DB
    → expand_via_hypergraph()
    → Obsidian note（或 direct result）

寫入流程：
  Execution → Flow 6 trigger
    → Hypergraph-DB add_v / add_e
    → Obsidian YAML frontmatter update
    → (可選) GenericAgent L3 技能結晶
```

---

## 5. 與原有設計文件的對應關係

| 本文（HG-06）| 來源文件 | 變更/共識 |
|------------|---------|---------|
| Hypergraph-DB 主 DB | HG-03, HG-04, HG-05 | **選定**，不再用 LanceDB 作為主力 |
| LanceDB → 向量加速層 | MEM_OPT, 7-FLOW, OSINT | 過渡方案，長期用 oMLX Jina 替代 |
| 六層記憶層次 | MEM_OPT + GenericAgent + HG-0A | 整合統一，覆蓋所有來源 |
| 統一 Vertex Schema | HG-03 + MEM_OPT + SALVA_V2 | 新增 lead + semantic_entry 類型 |
| Flow 6 具體化 | 7-FLOW（最大缺口）| 新定義 4 個步驟 |
| Keyword Graph → 超邊 | SALVA_V2 + HG-03 | 橋接，兩者不衝突 |
| Piper/Handy 定位 | Piper + Handy 指導文件 | 與 Hypergraph-DB 整合 |
| Obsidian 雙寫 | HG-03 + HG-0A | 共識，YAML frontmatter 同步 |

---

## 6. 待解決的具體問題

### 問題 A：Piper 的 Semantic Expansion 引擎需要接入 oMLX Jina
**狀態：** 設計在 Piper 文件中，未驗證是否可實際運行
**下一步：** 讀取 Piper 完整代碼（如果有），確認 oMLX Jina 接口

### 問題 B：Handy 的 Feedback Loop 從未與 Hypergraph-DB 對接
**狀態：** Handy 設計完整，但反饋信號寫入哪裡從未定義
**下一步：** 把 Handy 的 feedback signal 接入 Flow 6 Step 6.2

### 問題 C：SALVA_V2 的 Layer 5 需要重新定義
**原有定義：** Layer 5 = Structured Lead Store + Vector DB
**新定義：** Layer 5 = Hypergraph-DB（結構）+ oMLX Jina（向量）+ Obsidian（人讀）

### 問題 D：BDDB SQLite 與 Hypergraph-DB 的邊界
**問題：** BDDB 是外部數據庫，與 Hypergraph-DB 的關係？
**答案：** BDDB = Layer 5 外部數據，Hypergraph-DB 可以引用 BDDB 的記錄作為 leaf 節點

---

## 7. 三個解決方案（根據整合結論重寫）

### 方案 A：最小可行（MVP，1-2週）

```
目標：驗證核心假設（Hypergraph-DB 能表達 Ryan 的實際關係）

Step 1：手工建立前 10 個頂點
  - person: Ryan
  - person: Emily
  - topic: hypergraph-memory
  - topic: job-search
  - topic: BD-leads
  - skill: salva-dive
  - lead: Momotoy
  - session: 2026-04-18

Step 2：建立有意義的超邊
  - person_context(Ryan, Emily)
  - topic_cluster(Ryan, hypergraph-memory, skill:hypergraph-skill)
  - lead_market_cluster(Momotoy, Japan, ArtToy)

Step 3：Jina embedding 驗證檢索
  - 向量預篩 → 結構擴展 → 結果有意義？

產出：schema 是否靠譜的明確答案
```

### 方案 B：整合 BD 7-Flow Flow 6（1個月）

```
目標：把 Flow 6 具體化，接入 Hypergraph-DB

Step 1：實現 Flow 6 四步
  - 6.1 Lead 寫入
  - 6.2 經驗萃取（Handy feedback）
  - 6.3 Obsidian 雙寫
  - 6.4 Hop 查詢

Step 2：Piper → Flow 6 觸發
  - Piper 意圖路由
  - 觸發 Flow 6 的時機判斷

Step 3：SALVA_V2 Keyword Graph 接入
  - 關鍵詞作為 topic vertex
  - 關鍵詞關係作為 keyword_relation hyperedge

產出：BD leads 系統有真正的記憶沉澱
```

### 方案 C：完整重構（長期）

```
目標：Hypergraph-DB 作為所有記憶的唯一真實來源

-廢除 LanceDB（因為從未跑起來）
- Hypergraph-DB 完全替代
- Piper = Hypergraph 攝入層
- Handy = Hypergraph 反饋層
- Salva = Hypergraph 擴展層
-Obsidian 雙寫

產出：完整的 Hypergraph-first Agent OS
```

---

## 8. 下一步行動

| 優先級 | 行動 | 對應 |
|-------|------|------|
| P0 | **方案 A：Hypergraph-DB MVP** | 驗證核心假設 |
| P1 | Flow 6 四步實現 | 填補最大缺口 |
| P2 | Piper oMLX Jina 接口測試 | 確認工具鏈 |
| P3 | Handy → Flow 6.2 反饋接入 | 關閉反饋迴路 |
| P4 | SALVA_V2 Keyword Graph → hyperedge | 完成整合 |

---

## 附錄：與 HG-00 審計結論的對照

HG-06 整合後，三個未解決問題的狀態：

| 缺口（HG-00）| HG-06 解決方案 |
|-------------|--------------|
| LanceDB Count: 0 | Hypergraph-DB 替代，廢除 LanceDB |
| Flow 6 從未被定義 | 定義了四個具體步驟 |
| HG-04 幻覺（100+→18）| 已在 HG-04 正文修正 |

---

標籤：#integration #hypergraph #Flow-6 #schema #memory-layer #bridge
