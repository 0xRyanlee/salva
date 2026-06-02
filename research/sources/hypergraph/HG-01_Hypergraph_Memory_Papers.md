# Hypergraph Memory for AI Agents — 論文綜述

**Date:** 2026-04-18
**Sources:** arXiv:2602.05665 (Graph-based Agent Memory) / OpenReview ICLR 2026 (HGMEM)

---

## 一、Graph-based Agent Memory（arXiv:2602.05665）

**Title:** Graph-based Agent Memory: Taxonomy, Techniques, and Applications
**URL:** https://arxiv.org/html/2602.05665v1
**GitHub:** https://github.com/DEEP-PolyU/Awesome-GraphMemory

### 為何需要記憶

| LLM Agent 限制 | 記憶如何幫助 |
|---------------|-------------|
| Knowledge Cutoff | 外部儲存即時資料 |
| Tool Incompetence | 累積工具使用模式 |
| Performance Saturation | 從長期任務失敗中學習 |

### 四個記憶目標
1. **Personalization** — 捕捉用戶偏好、互動歷史
2. **Long-term Reasoning** — 超越上下文窗口的無界外部儲存
3. **Self-improving** — 累積經驗知識，無需重新訓練
4. **Hallucination Mitigation** — 基於結構化、可驗證的記憶內容

### 記憶操作（CRUD）

| 操作 | 形式定義 |
|------|---------|
| Write | `Write(m, M) → M'` |
| Read | `Read(q, M) → Mq` |
| Update | `Update(m, M) → M'` |
| Delete | `Delete(m, M) → M'` |

### 生命週期

```
EXTRACTION → STORAGE → RETRIEVAL → EVOLUTION
```

### 認知結構分類

| 類型 | 功能 |
|------|------|
| Semantic Memory | 一般世界知識、事實 |
| Procedural Memory | 技能、流程、規則 |
| Episodic Memory | 過去事件的時間序列 |
| Working Memory | 當前對話、思考緩衝 |

### 傳統 vs 圖結構記憶

**傳統：** Linear/Buffer（固定token窗口）→ 資訊丟失；Vector-based（語意搜索）→ 無結構推理

**圖結構優勢：**
- 顯式關係建模
- 層次化組織
- 時間/動態結構化
- 高效結構化檢索

---

## 二、HGMEM: Hypergraph-Based Memory（ICLR 2026）

**Paper:** https://openreview.net/pdf?id=coF6roWi9M

### 核心問題

現有 RAG 記憶機制的四個缺陷：
1. **被動儲存** — 累積孤立事實，不建模關聯
2. **靜態性質** — 無法形成高階關聯
3. **碎片化推理** — 全域理解能力弱
4. **二元邊限制** — 標準圖只能描述 ≤2 個節點的關係

### 超圖記憶結構

```
Memory M = (VM, EM)

Vertex vi = (Ω_ent_vi, D_vi)
  - Ω_ent_vi: 實體名稱和描述
  - D_vi: 關聯的文本塊

Hyperedge ej = (Ω_rel_ej, V_ej)
  - Ω_rel_ej: 關係描述
  - V_ej: 附屬節點集合（可 ≥2）
```

### 三個記憶演化操作

| 操作 | 功能 | 效果 |
|------|------|------|
| **Update** | 修訂現有超邊描述 | 精煉現有記憶點 |
| **Insertion** | 新增超邊 | 從檢索內容建立新記憶點 |
| **Merging** | 合併現有記憶點為單元 | **建立高階關聯** |

### Merging 公式

```python
Ω_rel_ek ← LLM(Ω_rel_ei, Ω_rel_ej, q̂)  # 生成統一描述
V_ek = V_ei ∪ V_ej                       # 合併附屬節點
```

### 自適應證據檢索策略

| 模式 | 使用時機 | 公式 |
|------|---------|------|
| **Local Investigation** | LLM 計劃深入調查特定記憶點 | `Vq = RN(V_ej)(q)` |
| **Global Exploration** | 探索當前記憶範圍外的面向 | `Vq = RC(M(t))(q)` |

### 實驗結果

| Dataset | GPT-4o | Qwen2.5-32B |
|---------|--------|-------------|
| Longbench (Comprehensiveness) | **65.73** | **64.18** |
| NarrativeQA (Acc) | **69.74%** | **66.51%** |
| NoCha (Acc) | **55.00%** | **51.00%** |

**移除 Merging 造成的性能下降 > 移除 Update** — 證明高階關聯建立的有效性

### 查詢類型分析

| 查詢類型 | Avg Entities/Hyperedge | Merging 效果 |
|----------|------------------------|-------------|
| Primitive（~3.5-3.9）| 低 | Merging 效果一般 |
| Sense-making（~5.3-8.0）| 高 | Merging **顯著提升**準確率 |

---

## 三、A Survey on Hypergraph Representation Learning（ACM 2022）

**URL:** https://iris.unito.it/retrieve/a596676c-9f0f-4790-a439-80cab5b46b37/A_Survey_on_Hypergraph_Representation_Learning.pdf

### 問題定義

超圖嵌入：學習一個映射函數
```
Φ : V → R|V|×d,  where d << |V|
```

將節點投影到潛在空間，同時保留結構和關係資訊。

### 三大家族

| 家族 | 核心思想 | 優點 | 缺點 |
|------|---------|------|------|
| **Spectral** | Laplacian 矩陣分解 | 理論扎實、可解釋 | 不能捕捉高階交互、擴展性差 |
| **Proximity-Preserving** | 保持鄰近性 | 更靈活 | 需要定義相似度函數 |
| **Neural Network** | 深度學習嵌入 | 捕捉複雜模式 | 可解釋性低 |

### 超圖 → 圖轉換的缺陷

| 轉換方式 | 描述 | 缺陷 |
|---------|------|------|
| Clique graph | 超邊→完全子圖 | 喪失群組概念，產生額外邊 |
| Star expansion | 超邊→二部圖節點 | 通過超邊節點間接交互 |
| Line graph | 超邊→節點 | 喪失組成資訊 |

---

## 對 Ryan 系統的啟發

### 短期（可直接落地）

1. **將 Hermes `MEMORY.md` / `USER.md` 視為 Semantic Memory**
   - 目前只有這兩層，缺少 Procedural / Episodic / Working 的分層
   - 可以新增 `~/.hermes/memories/procedural/` 存放技能腳本要點

2. **Obsidian vault 作為外部長期記憶**
   - `memory/` → Semantic（固化知識）
   - `tasks/` → Episodic（事件序列）
   - 符合 HGMEM 的 Write → Store → Retrieve → Evolution 生命週期

### 中期（超圖 skill 設計參考）

1. **知識節點（Vertex）= Obsidian vault 中的每篇 note**
2. **超邊（Hyperedge）= 主題標籤 + 雙向連結 + 時序關係**
3. **Merging 操作 = LLM 自動總結多篇相關 note 為更高層次的概念**

### 長期（記憶系統重構方向）

```
Hermes Memory System 目標架構：

┌─────────────────────────────────────────────┐
│  Working Memory (當前對話上下文)              │
├─────────────────────────────────────────────┤
│  Episodic Memory (Obsidian tasks/ 日誌)      │
├─────────────────────────────────────────────┤
│  Semantic Memory (Obsidian research/memory/)  │
├─────────────────────────────────────────────┤
│  Procedural Memory (Hermes skills/ + notes/)  │
└─────────────────────────────────────────────┘

           ↑  Hypergraph 連接層
      （主題 / 人 / 專案 / 時間 多維關係）
```

---

## 標籤

#hypergraph #memory-system #AI-agent #RAG #knowledge-graph
