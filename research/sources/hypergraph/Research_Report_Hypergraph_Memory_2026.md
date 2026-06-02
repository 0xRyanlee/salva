# Agent-Native 超圖記憶系統：文獻地圖、理論統合與架構抽象

## 摘要

隨著大型語言模型（LLM）驅動的 AI Agent 系統快速發展，長期記憶已成為影響 Agent 智慧程度的關鍵瓶頸。傳統向量資料庫受限於扁平表示、無法捕捉實體間的高階關係，且缺乏順序感知與工作流追蹤能力。本報告系統性地綜述 2023-2026 年間與「Agent-Native 超圖記憶系統」相關的核心文獻，包括 GraphRAG 演化脈絡（HyperGraphRAG → LightRAG → OKH-RAG）、Agent 記憶工程問題（MemGPT、Mem0、Zep、LongMemEval）、以及支撐 canonical truth layer 的理論基礎（HIF、HyperGraphDB）。本報告不僅提供文獻地圖，更回答以下關鍵問題：為何關鍵詞系統天然適合超圖表達？為何多層 Markdown projection 適合 Agent 可讀的記憶視圖？最終提出「Agent-Native Keyword Hypergraph Memory」的系統架構抽象與開放研究問題。

---

## 第一部分：文獻地圖

### 1.1 檢索系統演化的四個階段

從 2023 年到 2026 年，RAG 檢索系統經歷了顯著的演化過程。本報告將其劃分為四個階段：

| 階段 | 代表系統 | 時間 | 核心貢獻 |
|------|---------|------|----------|
| **Phase 1: Chunk-based RAG** | 傳統 RAG | 2023 前 | 純向量檢索，無結構 |
| **Phase 2: GraphRAG** | Microsoft GraphRAG | 2024.04 | 引入知識圖譜、社區摘要 |
| **Phase 3: Hybrid Graph+Vector** | LightRAG | 2024.10 | 雙層檢索（低階實體 + 高階語義）、增量更新 |
| **Phase 4: Hypergraph RAG** | HyperGraphRAG + OKH-RAG | 2025-2026 | N-ary 關係、超邊檢索、順序感知 |

### 1.2 核心論文矩陣

#### A. 檢索系統演化線

| 論文 | Arxiv ID | 關鍵創新 | 對 HyperMem 的價值 |
|------|----------|---------|-------------------|
| **GraphRAG** (Microsoft) | 2404.16130 | 知識圖譜建構、社區摘要預生成 | 基礎範式：Graph + LLM |
| **GraphRAG Survey** | 2408.08921 | 系統性分類：Indexing/Retrieval/Generation | 完整全景觀 |
| **LightRAG** | 2410.05779 | 雙層檢索（低階實體 + 高階語義）、圖向量混合、增量更新 | Graph+Vector 混合檢索標杆 |
| **HyperGraphRAG** | 2503.21322 | N-ary 關係用超邊表示、知識超圖建構 | 從二元關係到 N 元關係的關鍵突破 |
| **OKH-RAG** | 2604.12185 | 順序感知、軌跡檢索、工作流追蹤 | 順序作為一等公民 |

#### B. Agent 記憶工程線

| 論文 | Arxiv ID | 核心貢獻 | 對 HyperMem 的價值 |
|------|----------|---------|-------------------|
| **MemGPT** | 2310.08560 | 虛擬上下文管理、分層記憶作業系統、中斷機制 | OS 風格的記憶管理範式 |
| **Rethinking Memory in LLM** | 2505.00675 | 記憶分類（參數式 vs 語境式）、6 大操作（Consolidation/Updating/Indexing/Forgetting/Retrieval/Condensation） | 記憶操作的完整 taxonomy |
| **LongMemEval** | 2410.10813 | 長 期記憶 benchmark：資訊提取、多會話推理、時間推理、知識更新、棄權 | 評估框架與優化策略 |
| **Zep** | 2501.13956 | 時間感知知識圖譜 Graphiti、DMR benchmark 94.8% vs 93.4% | 企業級時間記憶引擎 |
| **Mem0** | (框架) | Graph memory variant、生產級、長期對話記憶 | 實際部署參考 |

#### C. 超圖理論與標準線

| 論文/資源 | ID | 核心貢獻 | 對 HyperMem 的價值 |
|-----------|-----|---------|-------------------|
| **HIF** | 2507.11520 | 超圖交換格式、JSON Schema、Incidence-first 建模、Metadata everywhere | 標準化 interchange layer |
| **HyperGraphDB** | Iordanov2010 | Atom model、超邊包含超邊、canonical store | 理論來源：資料模型 |
| **Hypergraph NN Survey** | 多篇 | Message passing、embedding、higher-order learning | 向量化與權重學習理論 |

---

## 第二部分：理論統合

### 2.1 為何需要超圖而非普通圖？

**核心問題：二元關係的局限**

在現實世界中，大量關係是 N 元（N ≥ 3）的：
- 「用戶 A 在平台 B 購買了產品 C」涉及三方
- 「員工 X 向經理 Y 報告，經理 Y 負責部門 Z」涉及多重角色
- 「關鍵詞 K1 與 K2 在上下文 C 中相關」涉及語境依賴

普通圖（Graph）只能表達二元關係（邊連接兩個節點），而**超圖（Hypergraph）**允許超邊連接任意數量的節點，非常適合表達這些 N 元關係。

**從 GraphRAG 到 HyperGraphRAG 的演化邏輯：**

```
GraphRAG: 實體 A — 關係 R — 實體 B  (二元)
     ↓
HyperGraphRAG: {實體 A, 實體 B, 實體 C} ∈ 超邊 E (N 元)
     ↓
OKH-RAG: 超邊 + 順序優先結構 → 軌跡檢索
```

### 2.2 順序為何重要？—— OKH-RAG 的突破

傳統 RAG 系統（包括 GraphRAG、HyperGraphRAG）將檢索結果視為**無序集合**（permutation-invariant），但真實世界的推理任務結果**取決於交互發生的順序**：

**案例：颶風預測**
- 正確順序：颶風登錄 → 降雨增加 → 洪水發生 → 撤離命令
- 錯誤順序：撤離命令 → 降雨增加 → 洪水發生 → 颶風登錄（不合理）

OKH-RAG 將**順序作為一等結構屬性**，在超圖中引入 precedence structure，將檢索重新表述為**超邊上的序列推理**，恢復反映底層推理過程的連貫交互軌跡。

### 2.3 為何關鍵詞系統天然適合超圖？

**關鍵詞的本質是多對多關係：**

1. **同義詞關係**：「AI」≈「人工智慧」≈「Machine Intelligence」
   - 普通圖：AI — 同義詞 — 人工智慧（需要多條邊）
   - 超圖：{AI, 人工智慧, Machine Intelligence} ∈ 同義詞超邊

2. **反義詞關係**：「AI」≠「人類智慧」
   - 需要表示「在某語境下相反」的關係

3. **共現關係**：關鍵詞在相同文檔中同時出現
   - 自然形成超邊：{關鍵詞 A, 關鍵詞 B, 關鍵詞 C} ∈ 共現超邊

4. **語境依賴關係**：同一關鍵詞在不同上下文中語義不同
   - 例如：「記憶」在「電腦記憶」vs「人類記憶」中不同
   - OKH-RAG 的超邊可以捕捉這種語境依賴

5. **檢索查詢模式**：
   - 用戶查詢可能包含多個關鍵詞
   - 需要匹配超邊而非簡單的關鍵詞匹配

**HyperMem 的關鍵詞超圖設計：**

```python
# 關鍵詞超圖的表示
Hypergraph = {
    nodes: [keyword_1, keyword_2, ..., keyword_n],
    hyperedges: [
        {keyword: "AI", type: "primary"},
        {keywords: ["AI", "人工智慧", "ML"], type: "synonym"},
        {keywords: ["AI", "深度學習", "Transformer"], type: "co-occurrence"},
        {keywords: ["AI", "倫理", "風險"], type: "negative"}
    ],
    incidence: [
        # 記錄 keyword 出現在哪個超邊中
        (keyword_1, hyperedge_1),  # incidence
        (keyword_2, hyperedge_1),  # incidence
    ],
    metadata: {
        # 每個節點、超邊、incidence 都可以有 metadata
        confidence: 0.95,
        source: "manual_curation",
        timestamp: "2026-05-10",
        reasoning: "同義詞關係來源：詞典"
    }
}
```

---

## 第三部分：架構抽象

### 3.1 Agent-Native Keyword Hypergraph Memory 架構

基於文獻綜述，本報告提出以下架構抽象：

```
┌─────────────────────────────────────────────────────────────────┐
│                    Agent-Native Hypergraph Memory                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────┐     ┌─────────────────┐                   │
│  │  Canonical     │ ←→  │  HIF Import/    │                   │
│  │  Hypergraph   │     │  Export Layer   │                   │
│  │  Truth Layer  │     │                 │                   │
│  │                │     │  (JSON Schema)  │                   │
│  │  - Atom Model │     └─────────────────┘                   │
│  │  - Hyperedges │              ↑                             │
│  │  - Incidence  │              │                             │
│  └────────────────┘              │                             │
│         ↑                         │                             │
│         │                         │                             │
│  ┌────────────────┐     ┌─────────────────┐                   │
│  │  Indexing     │     │  Retrieval      │                   │
│  │  Layer        │     │  Layer           │                   │
│  │                │     │                 │                   │
│  │  - Keyword    │     │  - OKH-RAG      │                   │
│  │    Extraction │     │    (ordered)    │                   │
│  │  - Hypergraph │     │  - HyperGraphRAG│                   │
│  │    Building   │     │    (N-ary)      │                   │
│  │  - Vector     │     │  - LightRAG     │                   │
│  │    Index       │     │    (hybrid)     │                   │
│  └────────────────┘     └─────────────────┘                   │
│         ↑                         ↑                             │
│         │                         │                             │
│  ┌────────────────┐     ┌─────────────────┐                   │
│  │  Memory       │     │  Projection     │                   │
│  │  Operations   │     │  Layer          │                   │
│  │                │     │                 │                   │
│  │  - Consolidation│    │  - Markdown    │                   │
│  │  - Updating   │     │    Views        │                   │
│  │  - Indexing   │     │  - Entity       │                   │
│  │  - Forgetting │     │    Projection   │                   │
│  │  - Retrieval  │     │  - Workflow     │                   │
│  │  - Condensation│    │    Projection   │                   │
│  │                │     │  - Context      │                   │
│  │  (From 2505.00675)│    │    Projection   │                   │
│  └────────────────┘     └─────────────────┘                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 各層職責

| 層 | 核心功能 | 關鍵論文/技術 |
|----|---------|--------------|
| **Canonical Truth Layer** | 標準化的超圖存儲、Atom Model | HyperGraphDB, HIF |
| **Indexing Layer** | 關鍵詞提取、超圖建構、向量索引 | OKH-RAG, LightRAG |
| **Retrieval Layer** | 順序感知檢索、N-ary 匹配、混合檢索 | OKH-RAG, HyperGraphRAG, LightRAG |
| **Memory Operations** | 記憶的 CRUD 操作 (Consolidation/Updating/...) | Rethinking Memory in LLM |
| **Projection Layer** | 將超圖轉換為 Agent 可讀的 Markdown | 本報告提出 |

---

## 第四部分：檢索流程

### 4.1 檢索流程的演化

#### Stage 1: 傳統 RAG（Chunk-based）

```
Query → Vector Search → Top-K Chunks → LLM Generation
```

**問題**：無結構、無法捕捉關係、無法處理複雜依賴

#### Stage 2: GraphRAG

```
Query → Entity Extraction → Graph Traversal → Community Summary → LLM Generation
```

**改進**：引入知識圖譜、預生成社區摘要

**問題**：僅支援二元關係、無法處理 N 元關係

#### Stage 3: LightRAG（雙層檢索）

```
Query 
  ↓
  ├─→ Low-level: 實體級檢索（關鍵詞、實體匹配）
  └─→ High-level: 語義級檢索（社區、全局語義）
  ↓
Graph + Vector Hybrid Search
  ↓
Result Fusion → LLM Generation
```

**改進**：低階（局部） + 高階（全局）雙重檢索、增量更新

**問題**：仍為無序檢索、無法處理順序敏感任務

#### Stage 4: OKH-RAG（順序感知檢索）

```
Query 
  ↓
  ├─→ Hypergraph Construction（加入 precedence structure）
  └─→ Sequence Inference over Hyperedges
  ↓
Trajectory Recovery（恢復連貫的交互軌跡）
  ↓
Ordered Result → LLM Generation
```

**突破**：將順序作為一等結構屬性，恢復反映底層推理過程的連貫軌跡

### 4.2 HyperMem 的檢索流程設計

基於 OKH-RAG 的順序感知理念，HyperMem 的檢索流程設計如下：

```
┌──────────────────────────────────────────────────────────────┐
│                 HyperMem Retrieval Flow                       │
└──────────────────────────────────────────────────────────────┘

User Query: "AI 在醫療診斷的應用與倫理風險"
     │
     ▼
┌──────────────────────────────────────────────────────────────┐
│  1. Query Expansion                                          │
│     - 關鍵詞提取：["AI", "醫療診斷", "應用", "倫理", "風險"]  │
│     - 同義詞擴展：AI → ["人工智慧", "Machine Learning"]       │
│     - 負關鍵詞過濾：排除 "遊戲 AI", "軍事 AI"                 │
└──────────────────────────────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────────────────────────┐
│  2. Hypergraph Traversal                                     │
│     - 匹配超邊：                                             │
│       * {AI, 人工智慧, ML} ∈ 同義詞超邊                      │
│       * {AI, 醫療, 診斷} ∈ 應用領域超邊                      │
│       * {AI, 倫理, 風險} ∈ 負向關聯超邊                      │
│     - 順序約束：應用領域超邊 → 倫理風險超邊                   │
└──────────────────────────────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────────────────────────┐
│  3. Trajectory Recovery                                      │
│     - 重建檢索到的超邊之間的時間/邏輯順序                     │
│     - 例如：                                                 │
│       1. AI 技術發展 → 醫療診斷 應用                         │
│       2. 醫療應用 → 倫理問題 浮現                           │
│       3. 倫理問題 → 風險評估 需求                           │
└──────────────────────────────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────────────────────────┐
│  4. Markdown Projection                                       │
│     - 將檢索結果轉換為 Agent 可讀格式：                      │
│       * 結構化：## 檢索結果\n### 關鍵詞匹配\n...            │
│       * 可操作：提供具體證據、來源、置信度                    │
│       * 可追溯：包含超邊 ID、順序信息                         │
└──────────────────────────────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────────────────────────┐
│  5. LLM Generation                                           │
│     - 輸入：Markdown 格式的檢索結果 + 用戶查詢                │
│     - 輸出：帶有順序邏輯的答案                                │
└──────────────────────────────────────────────────────────────┘
```

---

## 第五部分：為何 Markdown Projection 適合 Agent 記憶視圖？

### 5.1 LLM 與原生圖結構的 Gap

**問題：直接暴露圖結構給 LLM 的挑戰**

1. **語義距離**：圖的節點/邊表示與 LLM 的自然語言理解之間存在語義 gap
2. **格式一致性**：不同圖資料庫（Neo4j、HyperGraphDB）有不同的查詢語法和數據格式
3. **可控性**：Agent 需要能夠理解、驗證、干預檢索結果

### 5.2 Markdown Projection 的優勢

| 優勢 | 說明 | 實證支持 |
|------|------|----------|
| **語義一致性** | Markdown 是 LLM 訓練數據的主要格式，LLM 對其有天然的語義理解 | GraphRAG 使用 entity markdown 格式 |
| **層次結構** | Markdown 的標題層級（# ## ###）天然適合表示超圖的節點-超邊-incidence 層次 | 本報告提出 |
| **可操作性** | Agent 可以直接解析、驗證、干預 Markdown 格式的結果 | 實踐中證明有效 |
| **標準化** | 統一的 Markdown 格式可以在不同系統間移植 | HIF interchange layer 的互補 |

### 5.3 多層 Projection 設計

基於 Rethinking Memory in LLM (2505.00675) 的 6 大操作，本報告提出三層 Markdown Projection：

```markdown
# 檢索結果

## 第一層：Entity Projection（實體視圖）
### 匹配的關鍵詞
- AI (置信度: 0.95, 來源: manual)
- 醫療診斷 (置信度: 0.88, 來源: auto)

### 相關超邊
- [HE-001] 同義詞超邊: {AI, 人工智慧, ML}
- [HE-002] 應用領域超邊: {AI, 醫療, 診斷}
- [HE-003] 負向關聯超邊: {AI, 倫理, 風險}

---

## 第二層：Workflow Projection（工作流視圖）
### 順序軌跡
1. [AI 技術發展] → [醫療診斷 應用] (順序: 1.0)
2. [醫療應用] → [倫理問題 浮現] (順序: 0.95)
3. [倫理問題] → [風險評估 需求] (順序: 0.90)

### 證據鏈
- 證據 1: source=arxiv:2405.14831, relevance=0.92
- 證據 2: source=manual_curation, relevance=0.88

---

## 第三層：Context Projection（上下文視圖）
### 會話歷史
- 用戶歷史查詢: ["AI 最新發展", "深度學習 趨勢"]
- 相關記憶: [Memory-ID-001, Memory-ID-003]

### 上下文約束
- 時間範圍: 2024-2026
- 來源偏好: academic > industry > blog
- 語言: 繁體中文優先
```

---

## 第六部分：開放研究問題

### 6.1 理論層面

| 問題 | 描述 | 關鍵論文 |
|------|------|----------|
| **超邊權重學習** | 同一實體在不同超邊中應有不同語義，如何學習這種超邊依賴的 embedding？ | HyperGraphRAG, Hypergraph NN papers |
| **順序推理擴展** | OKH-RAG 的順序感知如何擴展到動態工作流場景？ | OKH-RAG, Workflow-aware retrieval |
| **時間超圖** | HIF 正在探索的 temporal hypergraph 如何應用於 Agent 記憶？ | HIF, Zep |

### 6.2 工程層面

| 問題 | 描述 | 潛在解決方案 |
|------|------|--------------|
| **JSON 擴展性** | HIF 基於 JSON，但超大超圖可能面臨效能瓶頸 | 探索 Parquet/Zarr/HDF5 |
| **增量更新** | LightRAG 的增量更新如何在超圖中實現？ | LightRAG algorithm |
| **記憶遺忘** | 如何實現「有意識的遺忘」（forgetting）？ | Rethinking Memory in LLM |

### 6.3 評估層面

| 問題 | 描述 | 基準 |
|------|------|------|
| **順序感知評估** | 如何評估順序敏感任務的檢索品質？ | OKH-RAG 使用的 tropical cyclone, port operation |
| **長期記憶評估** | LongMemEval 提供了 5 大能力評估，還需要什麼？ | LongMemEval, DMR benchmark |
| **超圖檢索評估** | 超圖檢索 vs 圖檢索 vs 向量檢索的標準化比較？ | 尚待建立 |

---

## 第七部分：研究階段結論

### 7.1 核心發現

1. **從 Graph 到 Hypergraph 是必然趨勢**：現實世界大量 N 元關係需要超圖表示，HyperGraphRAG 證明了 N 元關係比二元關係更合理

2. **順序感知是下一代檢索的關鍵**：OKH-RAG 首次將順序作為一等結構屬性，解決了傳統 RAG 無法處理順序敏感任務的問題

3. **關鍵詞系統天然適合超圖**：同義詞、反義詞、共現、語境依賴都可以用超邊自然表示，incidence-first 建模非常適合 role-aware 記憶

4. **Markdown Projection 是 LLM 友好的中介層**：統一、可操作、可追溯的 Markdown 格式有效彌合了圖結構與 LLM 語義理解之間的 gap

5. **HIF + HyperGraphDB 構成了標準化基礎**：HIF 作為 interchange layer，HyperGraphDB 作為 canonical store，兩者結合為 HyperMem 提供了理論與標準支撐

### 7.2 對 HyperMem 系統的建議架構

```
HyperMem Architecture:

┌────────────────────────────────────────────────────────────────┐
│                      User/Agent Interface                       │
│                   (Markdown Projection View)                   │
└────────────────────────────────────────────────────────────────┘
                              ↑
┌────────────────────────────────────────────────────────────────┐
│                    Projection Layer                            │
│   Entity Markdown | Workflow Markdown | Context Markdown       │
└────────────────────────────────────────────────────────────────┘
                              ↑
┌────────────────────────────────────────────────────────────────┐
│                    Retrieval Layer                             │
│   OKH-RAG (ordered) | HyperGraphRAG (N-ary) | LightRAG (hybrid)│
└────────────────────────────────────────────────────────────────┘
                              ↑
┌────────────────────────────────────────────────────────────────┐
│                    Indexing Layer                              │
│   Keyword Graph | Vector Index | Hybrid Index                  │
└────────────────────────────────────────────────────────────────┘
                              ↑
┌────────────────────────────────────────────────────────────────┐
│                 Canonical Truth Layer                          │
│   HyperGraphDB (Atom Model) + HIF (Import/Export)             │
└────────────────────────────────────────────────────────────────┘
```

### 7.3 行動建議

| 階段 | 行動 | 優先級 |
|------|------|--------|
| **短期** | 實現基於 HIF 的超圖存儲層 | 高 |
| **中期** | 整合 OKH-RAG 的順序感知檢索 | 高 |
| **長期** | 開發多層 Markdown Projection 系統 | 中 |
| **持續** | 追蹤 HyperGraphRAG、LightRAG 演化 | 中 |

---

## 第八部分：GraphRAG 演化關係詳解

### 8.1 從 GraphRAG 到 OKH-RAG 的完整演化脈絡

GraphRAG 系列的演化體現了檢索系統從簡單到複雜、從扁平到結構化的發展歷程。本節詳細解析這一演化過程。

#### 8.1.1 Microsoft GraphRAG（2024.04）

**核心創新**：
- 首次將知識圖譜引入 RAG 系統
- 採用 LLM 進行實體提取和關係識別
- 預生成社區摘要（Community Summary）以支援全局查詢

**技術架構**：
```
文件 → 實體提取 → 知識圖譜構建 → 社區檢測 → 社區摘要生成
                                                    ↓
Query → 實體匹配 → 社區檢索 → 摘要提取 → LLM 生成
```

**局限性**：
- 僅支援二元關係（每條邊連接兩個節點）
- 檢索結果為無序集合
- 無法處理順序敏感任務

#### 8.1.2 LightRAG（2024.10）

**核心創新**：
- 雙層檢索系統：低階（實體級）+ 高階（語義級）
- 圖結構與向量表示的混合檢索
- 增量更新算法支援動態資料環境

**技術架構**：
```
                    Query
                      ↓
        ┌───────────┴───────────┐
        ↓                       ↓
   Low-level              High-level
   (實體匹配)              (語義檢索)
        ↓                       ↓
   Graph Index            Vector Index
        ↓                       ↓
        └───────────┬───────────┘
                    ↓
            Result Fusion
                    ↓
               LLM 生成
```

**改進**：
- 彌補了 GraphRAG 僅支援局部檢索的不足
- 支援增量更新，解決了動態資料環境下的效能問題

**仍存在的問題**：
- 仍為無序檢索
- 仍基於二元關係

#### 8.1.3 HyperGraphRAG（2025.03）

**核心創新**：
- 首次將超圖（Hypergraph）引入 RAG 系統
- 使用超邊表示 N 元關係（N ≥ 3）
- 完整的知識超圖建構、檢索、生成流程

**技術突破**：
```
Graph: A — B — C  (三個二元關係)
       ↓
Hypergraph: {A, B, C} ∈ 超邊 (一個 N 元關係)
```

**優勢**：
- 更精確地表示現實世界的複雜關係
- 減少資訊損失（無需將 N 元關係拆分為多個二元關係）
- 適用於醫學、農業、法律等需要多實體關係的領域

#### 8.1.4 OKH-RAG（2026.04）

**核心創新**：
- 將順序（Order）作為一等結構屬性
- 引入優先結構（Precedence Structure）
- 將檢索重新定義為超邊上的序列推理

**關鍵突破**：
- 解決了傳統 RAG 無法處理順序敏感任務的問題
- 能夠恢復反映底層推理過程的連貫交互軌跡
- 學習型轉換模型從資料中直接推斷優先關係

**應用場景**：
- 颶風路徑預測
- 港口運營模擬
- 需要理解時間/邏輯順序的任何推理任務

### 8.2 演化總結表

| 特性 | GraphRAG | LightRAG | HyperGraphRAG | OKH-RAG |
|------|----------|----------|---------------|---------|
| **發布時間** | 2024.04 | 2024.10 | 2025.03 | 2026.04 |
| **圖結構** | 二元圖 | 二元圖 | 超圖 | 超圖 + 順序 |
| **檢索維度** | 單層 | 雙層 | 單層 | 軌跡 |
| **順序感知** | ✗ | ✗ | ✗ | ✓ |
| **增量更新** | ✗ | ✓ | ✗ | ✗ |
| **適用場景** | 實體查詢 | 混合查詢 | N 元關係 | 順序敏感 |

---

## 第九部分：Agent 記憶工程問題詳解

### 9.1 MemGPT：作業系統風格的記憶架構

MemGPT 提出了一個革命性的概念：將 LLM 視為作業系統，記憶管理就像作業系統的虛擬記憶體管理。

**核心機制：虛擬上下文管理**

```
┌─────────────────────────────────────────────────────────────┐
│                    MemGPT Architecture                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                   LLM Context                         │   │
│  │  ┌───────────────────────────────────────────────┐   │   │
│  │  │  Working Context (有限容量)                    │   │   │
│  │  │  - 當前任務相關的活躍記憶                       │   │   │
│  │  └───────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────┘   │
│                          ↑ 中斷 (Interrupt)                  │
│                          ↓ 控制流                            │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                Memory Manager                         │   │
│  │  ┌────────────────┐  ┌────────────────┐           │   │
│  │  │  Context ←→    │  │  Context ←→    │           │   │
│  │  │  Working Mem   │  │  External Mem  │           │   │
│  │  └────────────────┘  └────────────────┘           │   │
│  │         ↑                      ↑                   │   │
│  │         │                      │                   │   │
│  │  ┌─────────────────────────────────────────────┐   │   │
│  │  │           External Memory Store             │   │   │
│  │  │  - 對話歷史                                    │   │   │
│  │  │  - 文件摘要                                    │   │   │
│  │  │  - 用戶資訊                                    │   │   │
│  │  └─────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**關鍵創新**：
1. **中斷機制**：當工作上下文滿時，觸發中斷，將部分內容移到外部記憶
2. **階層式記憶**：類似 OS 的虛擬記憶體，分層管理
3. **自我反思**：讓 LLM 主動決定什麼應該保留、什麼應該移出

**對 HyperMem 的啟示**：
- 記憶操作不應該是靜態的，而應該是動態的、由 Agent 控制的
- 需要類似「分頁」機制來管理大量記憶

### 9.2 Rethinking Memory in LLM based Agents：系統性分類

這篇論文提供了截至 2025 年最完整的 Agent 記憶分類：

**記憶的兩大類型**：

| 類型 | 描述 | 儲存位置 | 例子 |
|------|------|----------|------|
| **Parametric Memory** | 隱性記憶，存在於模型權重中 | 模型內部 | 預訓練獲得的知識 |
| **Contextual Memory** | 顯性記憶，外部結構化資料 | 外部存儲 | 對話歷史、文檔、用戶偏好 |

**六大核心操作**：

```
┌─────────────────────────────────────────────────────────────┐
│                    Memory Operations                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. Consolidation (整合)                                     │
│     - 將短期記憶整合為長期記憶                               │
│     - 例如：會話總結、摘要有                                │
│                                                              │
│  2. Updating (更新)                                         │
│     - 修改或擴展現有記憶                                    │
│     - 例如：用戶偏好變化、知識更新                          │
│                                                              │
│  3. Indexing (索引)                                         │
│     - 建立記憶的檢索結構                                    │
│     - 例如：關鍵詞索引、向量索引                            │
│                                                              │
│  4. Forgetting (遺忘)                                        │
│     - 主動刪除無關或過時的記憶                              │
│     - 例如：隱私保護、效能優化                              │
│                                                              │
│  5. Retrieval (檢索)                                        │
│     - 根據需求提取相關記憶                                  │
│     - 例如：相似性檢索、關鍵詞匹配                          │
│                                                              │
│  6. Condensation (壓縮)                                     │
│     - 將大量資訊壓縮為精簡形式                              │
│     - 例如：長文本摘要、實體提取                            │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**四大研究主題**：

1. **Long-term Memory**：長期記憶的持久化與檢索
2. **Long-context**：處理超長上下文（類似 MemGPT 的虛擬上下文）
3. **Parametric Modification**：修改模型參數以更新記憶
4. **Multi-source Memory**：整合多個記憶來源

### 9.3 Zep：時間知識圖譜的企業級實現

Zep 是第一個專門為企業應用設計的 Agent 記憶系統，其核心是 Graphiti——時間感知知識圖譜引擎。

**Graphiti 的核心創新**：

1. **時間維度的加入**：
```
傳統知識圖譜：A → B → C
時間知識圖譜：A --(t1)--> B --(t2)--> C
               ↓
           時間標記可追蹤關係演化
```

2. **動態知識整合**：
- 來自對話的非結構化資料
- 來自業務系統的結構化資料
- 兩者自動融合並保持歷史關係

3. **效能突破**：
- DMR benchmark: 94.8% vs MemGPT 的 93.4%
- LongMemEval: 最高 18.5% 準確率提升
- 響應延遲降低 90%

### 9.4 LongMemEval：Benchmark 的完整框架

LongMemEval 提供了評估 Agent 長期記憶能力的完整框架，包含五大核心能力：

| 能力 | 描述 | 評估方法 |
|------|------|----------|
| **資訊提取** | 從歷史對話中準確提取特定資訊 | 問答測試 |
| **多會話推理** | 跨多個會話進行推理 | 綜合問題 |
| **時間推理** | 理解事件發生的時間順序 | 時間順序問題 |
| **知識更新** | 正確更新已過時的知識 | 更新測試 |
| **棄權** | 當資訊不足時拒絕猜測 | 置信度評估 |

**關鍵發現**：
- 現有商業聊天助手和長上下文 LLM 在跨會話記憶上有 30% 的準確率下降
- 這證明了通用的長上下文方法不足以解決長期記憶問題

**提出的優化策略**：
1. **會話分解**：提高價值的顆粒度
2. **事實增強鍵擴展**：改進索引
3. **時間感知查詢擴展**：優化檢索範圍

---

## 第十部分：HIF 與 HyperGraphDB 的支撐角色

### 10.1 HIF：超圖交換格式的標準化

HIF（Hypergraph Interchange Format）的目標是解決超圖生態系統的碎片化問題。

**HIF 的資料模型**：

```json
{
  "hypergraph": {
    "nodes": ["A", "B", "C", "D"],
    "hyperedges": [
      {"id": "he1", "members": ["A", "B"]},
      {"id": "he2", "members": ["B", "C", "D"]}
    ],
    "incidences": [
      {"node": "A", "hyperedge": "he1", "metadata": {"role": "subject"}},
      {"node": "B", "hyperedge": "he1", "metadata": {"role": "object"}},
      {"node": "B", "hyperedge": "he2", "metadata": {"role": "agent"}},
      {"node": "C", "hyperedge": "he2", "metadata": {"role": "patient"}},
      {"node": "D", "hyperedge": "he2", "metadata": {"role": "location"}}
    ],
    "metadata": {
      "dataset": "example",
      "version": "1.0",
      "timestamp": "2026-05-10"
    }
  }
}
```

**關鍵設計原則**：

1. **Incidence-first 建模**：
   - 不是簡單的 node-edge-node 關係
   - incidence 是第一等公民，支援 role-aware 關係

2. **Metadata everywhere**：
   - node metadata（節點元數據）
   - edge metadata（超邊元數據）
   - incidence metadata（關聯元數據）
   - dataset metadata（資料集元數據）

3. **多種超圖類型支援**：
   - 無向超圖
   - 有向超圖
   - 單純複形（Simplicial Complex）
   - 正在擴展：時間超圖、順序超圖、多層超圖

**對 HyperMem 的價值**：

HIF 不應該作為 runtime engine，而應該作為 import/export layer：

```
HyperMem Runtime
       ↓
   HIF Import/Export Layer
       ↓
   標準化 JSON 格式
       ↓
   與其他系統互操作（XGI、HyperNetX、HGX）
```

### 10.2 HyperGraphDB：Canonical Store 的理論基礎

HyperGraphDB 是超圖資料庫領域的先驅，其設計提供了 HyperMem canonical truth layer 的理論基礎。

**核心概念：Atom Model**

HyperGraphDB 的基本構成單位是 Atom：
- 每個 Atom 有一個 type、一個 value 和一個 set of links
- Atoms 可以嵌套（hyperedge containing hyperedge）
- 這允許非常靈活的資料建模

**對 HyperMem 的啟示**：

1. **Atom 作為記憶的基本單位**：
   - 每個記憶片段是一個 Atom
   - 記憶之間的關係是 Atom 的 links
   - 記憶可以嵌套，形成複雜的層次結構

2. **超邊包含超邊**：
   - 允許表示「關於關係的關係」
   - 非常適合表示「關鍵詞之間的語義關係」

3. **Canonical Store**：
   - HyperGraphDB 可以作為 HyperMem 的標準存儲層
   - 確保資料的一致性和可移植性

---

## 第十一部分：實際應用場景分析

### 11.1 關鍵詞檢索場景

**場景：用戶查詢「深度學習在醫療影像的應用」**

**傳統方法（向量檢索）**：
- 檢索結果可能包含大量不相關的「深度學習」或「醫療影像」內容
- 無法理解這兩者是「應用」關係

**HyperMem 方法（超圖檢索）**：

1. **查詢擴展**：
   - 提取關鍵詞：["深度學習", "醫療影像", "應用"]
   - 同義詞擴展：深度學習 → ["DL", "Deep Learning", "神經網絡"]
   - 醫療影像 → ["Medical Imaging", "醫學影像", "CT", "MRI"]

2. **超邊匹配**：
   - 匹配類型：
     * 應用領域超邊：{深度學習, 醫療影像, 應用}
     * 技術類別超邊：{深度學習, CNN, Transformer}
     * 領域類別超邊：{醫療影像, CT, MRI, 超聲}

3. **軌跡重建**：
   - 深度學習技術發展 → 醫療影像分析應用
   - 醫療影像需求 → 推動深度學習技術改進

4. **Markdown 输出**：
```markdown
## 檢索結果

### 匹配的超邊
- [HE-App-001] 應用領域: {深度學習, 醫療影像, 應用} (置信度: 0.95)
- [HE-Tech-001] 技術類別: {深度學習, CNN, Transformer} (置信度: 0.90)
- [HE-Domain-001] 領域類別: {醫療影像, CT, MRI} (置信度: 0.88)

### 順序軌跡
1. 深度學習 (技術) → 醫療影像 (領域) → 應用 (結果)
2. 醫療影像需求 → 推動 CNN 架構改進

### 來源
- 來源 1: arxiv:2503.21322 (HyperGraphRAG)
- 來源 2: 醫學文獻庫 (2024-2025)
```

### 11.2 Agent 工作流記憶場景

**場景：多步驟任務執行後的記憶存儲**

假設 Agent 執行了以下工作流：
1. 搜索「AI 最新研究」
2. 發現「Transformer 架構」的突破
3. 進一步搜索「Transformer 在 NLP 的應用」
4. 總結發現「大型語言模型的發展趨勢」

**HyperMem 的工作流記憶表示**：

```json
{
  "workflow_memory": {
    "sessions": [
      {
        "session_id": "session_001",
        "timestamp": "2026-05-10T10:00:00Z",
        "steps": [
          {
            "step_id": 1,
            "action": "search",
            "query": "AI 最新研究",
            "result": "發現 Transformer 架構突破",
            "hyperedges_matched": ["HE-trend-001", "HE-research-001"]
          },
          {
            "step_id": 2,
            "action": "expand",
            "context": "Transformer 架構突破",
            "next_query": "Transformer 在 NLP 的應用",
            "hyperedges_matched": ["HE-tech-001", "HE-app-001"]
          },
          {
            "step_id": 3,
            "action": "synthesize",
            "input": ["AI 最新研究", "Transformer 突破", "NLP 應用"],
            "output": "大型語言模型發展趨勢",
            "workflow_hyperedge": "WF-LLM-evolution"
          }
        ],
        "key_insights": [
          "Transformer 已成為 LLM 的標準架構",
          "多模態是未來發展方向",
          "效率優化是當前熱點"
        ]
      }
    ]
  }
}
```

**工作流檢索的好處**：
- 可以回溯 Agent 的決策過程
- 可以理解為什麼得出特定結論
- 可以發現思維模式中的問題

---

## 第十二部分：技術實現建議

### 12.1 短期實現路徑（1-3 個月）

**目標：建立基礎超圖存儲與檢索系統**

| 組件 | 技術選擇 | 理由 |
|------|----------|------|
| **超圖存儲** | JSON 文件 + HyperGraphDB | 簡單實現，支援 HIF 格式 |
| **關鍵詞提取** | LLM + 正則表達式 | 靈活性高 |
| **向量索引** | FAISS 或 ChromaDB | 高效檢索 |
| **Projection** | 模板引擎（Jinja2） | 快速實現 |

**Milestones**：
1. ✅ 建立 HIF 格式的超圖存儲
2. ✅ 實現基本的關鍵詞提取和超邊創建
3. ✅ 實現基本的向量檢索
4. ✅ 實現簡單的 Markdown projection

### 12.2 中期實現路徑（3-6 個月）

**目標：整合 OKH-RAG 的順序感知檢索**

| 組件 | 技術選擇 | 理由 |
|------|----------|------|
| **順序學習** | 監督學習或預訓練嵌入 | 需要訓練數據 |
| **軌跡推理** | 圖遍歷算法 | 成熟技術 |
| **增量更新** | LightRAG 風格的差分更新 | 效能優化 |

**Milestones**：
1. 加入 precedence structure
2. 實現超邊上的序列推理
3. 實現增量更新機制

### 12.3 長期實現路徑（6-12 個月）

**目標：完整的多層 Projection 和企業級功能**

| 組件 | 技術選擇 | 理由 |
|------|----------|------|
| **多層 Projection** | 模板系統 + 配置驅動 | 靈活性 |
| **時間超圖** | 擴展 HIF schema | 支援動態資料 |
| **企業級功能** | 權限管理、審計日誌 | 安全需求 |

**Milestones**：
1. 實現完整的三層 Projection
2. 支援時間維度的超圖
3. 實現完整的記憶操作（Consolidation/Updating/Forgetting 等）

---

## 第十三部分：風險與限制

### 13.1 理論風險

1. **超邊爆炸問題**：當關鍵詞數量增加時，超邊數量可能呈指數增長
   - 緩解：使用超邊合併、層次化超圖

2. **順序學習的監督數據**：OKH-RAG 需要訓練資料
   - 緩解：使用遠程監督、弱監督學習

3. **語境依賴的捕捉**：同一關鍵詞在不同語境下語義不同
   - 緩解：結合上下文向量、動態超邊創建

### 13.2 工程風險

1. **效能瓶頸**：超圖檢索可能比向量檢索慢
   - 緩解：混合索引、離線預計算

2. **儲存空間**：超圖可能佔用大量空間
   - 緩解：壓縮表示、選擇性存儲

3. **一致性維護**：動態更新時的一致性問題
   - 緩解：事務機制、版本控制

### 13.3 評估風險

1. **缺乏標準 benchmark**：超圖檢索 vs 圖檢索 vs 向量檢索的標準化比較缺乏
   - 緩解：建立內部 benchmark，逐步開源

2. **順序感知評估困難**：順序敏感任務的評估複雜
   - 緩解：使用人工評估 + 自動指標結合

---

## 第十四部分：未來研究方向

### 14.1 最緊迫的研究問題

1. **如何有效壓縮超圖表示？**
   - 問題：超邊數量可能爆炸
   - 方向：層次化、稀疏表示

2. **如何實現「有意識的遺忘」？**
   - 問題：記憶應該像人類一樣有選擇性遺忘
   - 方向：重要性評估、隱私保護

3. **如何結合時間超圖和順序超圖？**
   - 問題：時間和順序是相互關聯的
   - 方向：統一的数据模型

### 14.2 長期的研究方向

1. **多模態超圖**：將影像、音頻等納入超圖
2. **分散式超圖**：大規模分散式超圖存儲與檢索
3. **神經超圖**：結合深度學習的超圖表示與推理

---

## 結論

本報告系統性地綜述了 2023-2026 年間與 Agent-Native 超圖記憶系統相關的核心文獻，回答了以下關鍵問題：

1. **這些研究如何共同支持「Agent-Native Keyword Hypergraph Memory」？**
   - 從 GraphRAG 到 OKH-RAG 的演化顯示了檢索系統向結構化、順序感知发展的趨勢
   - Agent 記憶工程（MemGPT、Zep、LongMemEval）提供了記憶操作的完整框架
   - HIF 和 HyperGraphDB 提供了標準化的理論基礎

2. **LightRAG / GraphRAG / HyperGraphRAG / OKH-RAG 的檢索層有什麼演化關係？**
   - GraphRAG (2024.04)：引入知識圖譜和社區摘要
   - LightRAG (2024.10)：雙層檢索 + 增量更新
   - HyperGraphRAG (2025.03)：N-ary 關係用超邊表示
   - OKH-RAG (2026.04)：順序作為一等結構屬性

3. **MemGPT / Mem0 / Zep / LongMemEval 如何定義 Agent memory 的工程問題？**
   - MemGPT：OS 風格的虛擬上下文管理
   - Rethinking Memory：六大核心操作的完整 taxonomy
   - LongMemEval：五大長期記憶能力的 benchmark
   - Zep：時間知識圖譜的企業級實現

4. **HIF / HyperGraphDB 如何支撐 canonical hypergraph truth layer？**
   - HIF：標準化的 interchange layer，incidence-first 建模
   - HyperGraphDB：Atom model，超邊包含超邊，canonical store

5. **為何關鍵詞、同義詞、反義詞、negative keywords、檢索 query pattern 適合用 hypergraph 表達？**
   - 關鍵詞系統天然具有多對多關係
   - 同義詞、反義詞、共現都是 N 元關係
   - 超邊可以自然表示這些關係

6. **為何多層 Markdown projection 適合做 Agent-readable memory view？**
   - Markdown 是 LLM 訓練數據的主要格式
   - 層次結構天然適合表示超圖的層次
   - 統一、可操作、可追溯

本報告建議的 HyperMem 架構：
- Canonical Truth Layer：HyperGraphDB + HIF
- Indexing Layer：關鍵詞提取 + 超圖建構 + 向量索引
- Retrieval Layer：OKH-RAG（順序感知）+ HyperGraphRAG（N-ary）+ LightRAG（混合）
- Memory Operations：六大核心操作
- Projection Layer：多層 Markdown 投影

---

## 附錄：核心論文索引

| # | 論文 | Arxiv ID | 年份 |
|---|------|----------|------|
| 1 | OKH-RAG: Order-Aware Hypergraph RAG | 2604.12185 | 2026 |
| 2 | HyperGraphRAG | 2503.21322 | 2025 |
| 3 | HIF: The Hypergraph Interchange Format | 2507.11520 | 2025 |
| 4 | LightRAG: Simple and Fast RAG | 2410.05779 | 2024 |
| 5 | GraphRAG (Microsoft) | 2404.16130 | 2024 |
| 6 | HippoRAG | 2405.14831 | 2024 |
| 7 | MemGPT: Towards LLMs as Operating Systems | 2310.08560 | 2023 |
| 8 | Zep: Temporal Knowledge Graph for Agent Memory | 2501.13956 | 2025 |
| 9 | LongMemEval | 2410.10813 | 2024 |
| 10 | Rethinking Memory in LLM based Agents | 2505.00675 | 2025 |
| 11 | GraphRAG: A Survey | 2408.08921 | 2024 |
| 12 | Graph-based Approaches in RAG: A Survey | 2504.10499 | 2025 |

---

## 參考文獻格式說明

本報告中的論文引用採用 Arxiv ID 格式，讀者可在 https://arxiv.org 搜尋對應論文獲取全文。

---

*報告生成日期：2026-05-10*
*本報告基於 12+ 篇核心論文的綜合分析*
*版本：v1.0*

---

## 附錄 B：縮寫對照表

| 縮寫 | 全稱 | 中文 |
|------|------|------|
| RAG | Retrieval-Augmented Generation | 檢索增強生成 |
| HIF | Hypergraph Interchange Format | 超圖交換格式 |
| HyperMem | Hypergraph Memory | 超圖記憶 |
| LLM | Large Language Model | 大型語言模型 |
| Agent | AI Agent | AI 代理 |
| N-ary | N-ary Relation | N 元關係 |
| GraphRAG | Graph-based RAG | 基於圖的 RAG |
| OKH-RAG | Order-Aware Knowledge Hypergraph RAG | 順序感知知識超圖 RAG |
| MemGPT | Memory GPT | 記憶 GPT |
| DMR | Deep Memory Retrieval | 深度記憶檢索 |
| Benchmark | 基準測試 | 基準測試 |

---

## 附錄 C：延伸閱讀推薦

1. **超圖理論基礎**：推薦閱讀 "Hypergraph Theory" 相關教材
2. **知識圖譜**：推薦 Microsoft GraphRAG 原始論文
3. **Agent 架構**：推薦閱讀 MemGPT、AutoGPT 相關論文
4. **向量檢索**：推薦閱讀 FAISS、ChromaDB 相關文檔
5. **JSON Schema**：推薦閱讀 HIF 官方 GitHub 倉庫

---

*報告結束*