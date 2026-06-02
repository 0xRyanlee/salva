# 超圖記憶系統完整技術調研

**Date:** 2026-04-18
**Status:** Completed — 技術路線封閉

---

## 一、超圖數學理論

### 1.1 形式定義

**超圖 H = (V, E)**
- V = 節點集合（vertices）
- E = 超邊集合（hyperedges），每條超邊是 V 的任意非空子集

**與普通圖的關鍵區別：**
- 普通圖：邊只連接 2 個節點（binary）
- 超圖：超邊可連接任意數量節點（n-ary）

### 1.2 核心矩陣表示

| 矩陣 | 維度 | 意義 |
|------|------|------|
| 關聯矩陣 H | \|V\| × \|E\| | h(v,e)=1 表示節點 v 在超邊 e 中 |
| 節點度矩陣 D_v | \|V\| × \|V\| | 對角線：每個節點的度 |
| 超邊度矩陣 D_e | \|E\| × \|E\| | 對角線：每條超邊的大小 |
| 超圖拉普拉斯 L | \|V\| × \|V\| | L = I - D_v^(-1/2) H W D_e^(-1) H^T D_v^(-1/2) |

### 1.3 關鍵定理

| 名稱 | 內容 |
|------|------|
| Berge-Fulkerson Conjecture | 每個 3-正則 3-均勻超圖有 2-因子覆蓋（未解決）|
| Erdős–Ko–Rado Theorem | n-均勻超圖的最大交錯家族大小 |
| Helly Property | 家庭中所有兩兩相交的集合都有共同交集 |

### 1.4 超圖類型分類

| 維度 | 類型 |
|------|------|
| 均勻性 | k-uniform（所有超邊大小=k）/ Non-uniform |
| 方向性 | Undirected / Directed（有父/子超邊）|
| 結構 | Simple / Multi-hypergraph（可有多重超邊）|
| 屬性 | Attributed（有節點特徵）/ Plain |
| 時間 | Static / Dynamic（時序超圖）|
| 節點關係 | Homogeneous / Heterogeneous |

---

## 二、超圖神經網絡（HGNN）

### 2.1 核心論文架構

**HGNN（arXiv:1809.09401）— 開山之作**

```python
# 單層 HGNN 前向傳播
X^(l+1) = σ(D_v^(-1/2) H W D_e^(-1) H^T D_v^(-1/2) X^(l) Θ^(l))
```

**三步驟：**
1. 節點特徵 → 超邊：H^T X（會聚）
2. 超邊權重調整：W D_e^(-1)
3. 超邊 → 節點：H（廣播）

**GCN 是 HGNN 的特例（當超邊大小=2時）**

### 2.2 後續演進

| 模型 | 年份 | 創新 |
|------|------|------|
| HGNN | 2018 | 開山框架，光譜卷積 |
| EHGNN | 2024 | 增強型，高光譜圖像分類 |
| MD-HGNN | 2025 | 多視角學習+結構學習 |
| HGNN-AS | 2025 | 注意力機制增強 |
| TF-HNN | 2023 | 無訓練超圖神經網絡 |

### 2.3 應用領域

| 領域 | 具體應用 |
|------|---------|
| 推薦系統 | 多行為序列建模、知識感知推薦 |
| 生物信息學 | 蛋白質複合物、基因調控網絡 |
| 社交網絡 | 群組互動、社區發現 |
| 電腦視覺 | 場景理解、姿態估計 |
| 藥物發現 | 分子建模、藥物-靶點交互 |

---

## 三、超圖信號處理（Hypergraph Signal Processing）

### 3.1 核心概念

類比普通圖信號處理：
- 圖傅立葉變換 → 超圖傅立葉變換
- 圖頻率 → 超圖頻率（特徵值）
- 圖濾波 → 超圖濾波

### 3.2 關鍵運算

```python
# 超圖信號 x 的傅立葉變換
x_hat = Φ^T x  # Φ = 超圖拉普拉斯矩陣的特徵向量

# 超圖信號捲積
g * x = Φ g(Λ) Φ^T x  # g(Λ) 是特徵值的濾波函數
```

### 3.3 高階全變差（Higher-Order Total Variation）

測量信號在超圖上的平滑度：
```python
TV_H(x) = sum_{e in E} w_e * sum_{(u,v) in e} (x_u - x_v)^2
```

---

## 四、超圖數據庫實現對比

### 4.1 三種主流方案

| 方案 | 語言 | 特點 | 缺點 |
|------|------|------|------|
| **Hypergraph-DB (iMoonLab)** | Python | 輕量、效能高（1M節點/200K超邊<7秒）、有視覺化、Apache 2.0 | 較新、生態不成熟 |
| **Graphbrain** | Python | Semantic Hypergraph、屬性丰富、支援 SQLite/LevelDB 後端、推理功能 | API 複雜、文件有限 |
| **HyperGraphDB (Kobrix)** | Java | 生產級、支援 P2P 複製、AGI 導向、成熟穩定 | 需要 JVM、非 Python 原生 |

### 4.2 性能對比（Hypergraph-DB）

| 規模 | 節點 | 超邊 | 總時間 |
|------|------|------|--------|
| 小規模 | 5,000 | 1,000 | 0.02s |
| 中規模 | 50,000 | 10,000 | 0.26s |
| 大規模 | 500,000 | 100,000 | 3.34s |
| 超大規模 | 1,000,000 | 200,000 | **6.60s** |

### 4.3 實測驗證（2026-04-18）

**Hypergraph-DB 0.3.0 安裝 + API 實測：**

```python
from hyperdb import HypergraphDB

db = HypergraphDB()
db.add_v("Ryan", {"role": "user"})
db.add_v("Emily", {"role": "partner"})
db.add_v("Hermes", {"role": "agent"})
db.add_v("Hypergraph-Skill", {"type": "skill"})
db.add_e(("Ryan", "Emily"), {"type": "relationship", "label": "戀人"})
db.add_e(("Ryan", "Hermes"), {"type": "interaction"})
db.add_e(("Ryan", "Hypergraph-Skill", "Emily"), {"type": "shared_context"})

print(f"頂點={db.num_v}, 超邊={db.num_e}")  # 4, 3
print(f"Ryan 鄰居: {db.nbr_v('Ryan')}")       # {'Emily', 'Hermes', 'Hypergraph-Skill'}
print(f"Ryan 的超邊: {db.nbr_e_of_v('Ryan')}")  # 3 個超邊（含三元超邊）

db.save("/tmp/ryan_memory.hg")  # 持久化
db2 = HypergraphDB.load("/tmp/ryan_memory.hg")  # 重載成功
```

**關鍵 API 發現：**
- `add_v(name, attrs_dict)` / `add_e((v1, v2, ...), attrs_dict)` — 簡潔
- `nbr_v(name)` → 鄰居節點集合（set）
- `nbr_e_of_v(name)` → 節點所屬超邊集合（元組set）
- `num_v` / `num_e` 是**屬性**，不是方法（不需括號）
- `degree_v(name)` / `degree_e(tuple)` — 圖論度
- `has_e(tuple_key)` — 超邊存在性查詢
- **不支持 `query_v`（NotImplementedError）** — 需自行實現搜索
- 默認存儲：`my_hypergraph.hgdb`（SQLite-like 格式）

**實測結論：**
- ✅ API 直覺，性能優秀
- ✅ 持久化可靠
- ✅ 支持任意 n 元超邊
- ⚠️ 全文搜索需要自己對接 embedding
- ⚠️ 需要自行實現基於 embedding 的相似度檢索

### 4.4 方案選擇

```
Ryan 系統需求評估：
✓ 個人知識庫規模（預估 <100K 節點）
✓ Python 優先（Hermes/Hypergraph skill 都是 Python）
✓ 需要與 Obsidian markdown 整合
✓ 需要向量化檢索（RAG 需求）

推薦：Hypergraph-DB（Python原生、性能優秀、可視化方便）
備選：Graphbrain（需要推理能力時）
```

---

## 五、記憶系統中的超圖應用

### 5.1 HGMEM（ICLR 2026）

**核心創新：** 超圖作為動態記憶結構

```python
# 記憶表示
M = (V_M, E_M)

# 節點 = 文本塊實體
v_i = (entity_name, chunk_text, embedding)

# 超邊 = 高階關係
e_j = (relation_description, {v_1, v_2, ..., v_n})

# 三個演化操作
Update:   M' = Update(existing_hyperedge, new_description)
Insert:   M' = M ∪ new_hyperedge
Merging:  M' = Merge(e_i, e_j)  # 建立高階關聯
```

**實驗結果：**
- Sense-making queries（複雜推理）：Merging 效果顯著
- Primitive queries（簡單事實）：Merging 效果一般
- 最佳性能在 t=3 步交互

### 5.2 HyperGraphRAG（arXiv:2503.21322）

**核心思想：** 將 n-ary 關係建模為單一超邊

```python
# 知識超圖結構
K = (V_K, E_K)

# 實體節點
v_j = {
    "name": str,           # 實體文本
    "type": str,           # 類型（Disease/Drug/Person...）
    "explain": str,        # 解釋
    "score": float         # 置信度
}

# 超邊（n-ary 事實）
e_i = {
    "text": str,           # 自然語言描述
    "score": float         # 置信度
}
```

**檢索策略：雙向擴展**
1. 實體檢索 → 找相關超邊
2. 超邊檢索 → 找相關實體
3. 融合：Local Investigation + Global Exploration

**性能對比（GraphRAG vs HyperGraphRAG）：**
| 任務 | GraphRAG | HyperGraphRAG |
|------|----------|---------------|
| 多實體關係問答 | 分解為多個二元關係 | 單一超邊完整捕獲 |
| 醫療診斷推理 | 需要多跳圖遍歷 | 一步超邊檢索 |

### 5.3 MemGPT（OS-inspired 分層記憶）

**三層記憶架構：**
```
┌─────────────────────────────────────────┐
│  Core Memory (上下文窗口)                 │
│  - 系統提示 / 人物設定                    │
├─────────────────────────────────────────┤
│  Recall Memory (外部向量檢索)              │
│  - 過去對話摘要 / 重要事實                 │
├─────────────────────────────────────────┤
│  Archival Memory (歸檔存儲)               │
│  - 長期冷數據 / 歷史記錄                  │
└─────────────────────────────────────────┘
```

**核心創新：**
- LLM 自主管理記憶「分頁」（類似 OS 虛擬記憶）
- 當上下文快滿時，自動總結並「換出」到召回記憶
- 記憶統計（memory stats）觸發主動檢索

### 5.4 LangGraph Memory

**四層記憶類型：**
| 類型 | 存儲內容 | Agent 示例 |
|------|---------|-----------|
| Semantic | 通用知識、人物設定 | 系統提示 |
| Episodic | 過去事件序列 | 對話歷史 |
| Procedural | 技能 SOP、工具使用 | Agent 指令 |
| Working | 當前任務狀態 | 對話緩衝 |

**持久化：**
```python
from langgraph.store.memory import InMemoryStore

# 支援命名空間隔離
store.put(namespace, key, value)  # 寫
item = store.get(namespace, key)  # 讀
store.search(namespace, query)    # 向量檢索
```

---

## 六、針對 Ryan 系統的技術路線

### 6.1 現有架構評估

```
現有記憶系統：
├── Hermes (~/.hermes/memories/)     → Semantic Memory（薄，2個md）
├── Obsidian (iCloud vault)          → Long-term Semantic + Episodic
├── BDDB SQLite                      → Procedural（封閉業務數據）
└── Sessions                         → Working Memory（對話歷史）
```

**缺口：**
1. 缺乏 Procedural Memory 結構化存儲
2. 缺乏超圖/圖結構的關係建模
3. 缺乏主動記憶檢索觸發機制

### 6.2 推薦技術棧

```
┌──────────────────────────────────────────────────────┐
│  Hypergraph Memory Layer (新建)                       │
├──────────────────────────────────────────────────────┤
│                                                       │
│  Hypergraph-DB (Python)  ←  輕量、效能優秀、視覺化    │
│                                                       │
│  節點 = Obsidian note 節點                     │
│  超邊 = 主題標籤 + 雙向連結 + 時序關係       │
│                                                       │
│  ┌───────────────────────────────────────────────┐   │
│  │  Node: (note_id, title, tags[], content_emb)  │   │
│  │  Hyperedge: (topic_id, {note_ids}, type)      │   │
│  └───────────────────────────────────────────────┘   │
│                                                       │
│  + Jina embedding (via oMLX)  → 向量化檢索          │
│  + HGNN 微調  →  節點/超邊嵌入學習                  │
│  + HGMEM Merging  →  自動高階關聯建立               │
│                                                       │
└──────────────────────────────────────────────────────┘
```

### 6.3 核心 Schema 設計

```python
# 節點定義
class MemoryNode:
    note_id: str           # Obsidian note ID
    title: str             # 標題
    content_hash: str      # 内容哈希
    embedding: list[float] # Jina v5 向量
    tags: list[str]        # 標籤
    node_type: str         # "person" / "topic" / "event" / "project"
    created_at: datetime
    updated_at: datetime

# 超邊定義
class MemoryHyperedge:
    hyperedge_id: str
    hyperedge_type: str    # "topic_cluster" / "timeline" / "relation" / "project"
    member_nodes: list[str] # 節點ID列表
    description: str       # LLM生成的描述
    confidence: float       # 置信度
    created_by: str        # "manual" / "llm_merge" / "system"
    created_at: datetime

# 超邊類型
TOPIC_CLUSTER = "topic_cluster"   # 主題聚合（如「超圖研究」）
TIMELINE = "timeline"              # 時序關係（如「2026-03-20 BD任務」）
SEMANTIC_RELATION = "semantic_relation"  # 語義關聯
PROJECT_CONTEXT = "project_context"      # 專案上下文
```

### 6.4 操作流程

```
日常記憶寫入：
1. 新對話結束 → 提取關鍵實體（LLM）
2. 更新 MemoryNode（如已存在則更新embedding）
3. 根據標籤/時序自動建立 Topic Hyperedge

Merging 操作（定期執行）：
1. 找到同一主題的多個 MemoryNode
2. LLM 生成統一的 MemoryHyperedge 描述
3. 合併為一個 topic_cluster 超邊
4. 標記為 "llm_merge"

檢索流程：
1. 查詢 → Jina embedding 相似度
2. 找到 top-k 相關 MemoryNode
3. 擴展 → 找這些節點所屬的所有 MemoryHyperedge
4. 雙向擴展 → 找到所有相關節點
5. 排序 → 返回給 LLM
```

---

---

## 七、Ryan 系統 Hypergraph Memory Schema（最終設計）

### 7.1 設計原則

1. **不做過度工程**：從 Obsidian vault 現有 markdown 直接映射
2. **超邊最小化**：只對「自然形成 n-ary 關係」的場景用超邊，不用超邊替代普通標籤
3. **嵌入優先檢索**：所有檢索走 Jina embedding 向量相似度，超圖結構用於關係擴展

### 7.2 Vertex 定義（Hypergraph-DB 頂點）

| 頂點類型 | 說明 | 屬性 |
|---------|------|------|
| `note:{path}` | Obsidian note 節點 | title, tags, content_hash, embedding |
| `person:{name}` | 人物節點 | name, role, description, embedding |
| `topic:{name}` | 主題節點 | name, category, embedding |
| `skill:{name}` | 技能節點 | name, category, description |
| `session:{id}` | 對話 session 節點 | id, timestamp, summary |

### 7.3 Hyperedge 定義（超邊）

| 超邊類型 | 描述 | 成員 | 建立方式 |
|---------|------|------|---------|
| `topic_cluster` | 主題聚合 | 3+ 個 note/topic 節點 | LLM Merging |
| `person_context` | 人物上下文 | 1 個 person + N 個 note/skill 節點 | 自動建立 |
| `project_timeline` | 專案時序 | 2+ 個 session 節點 | 自動建立 |
| `skill_dependency` | 技能依賴 | 2+ 個 skill 節點 | 自動建立 |
| `conversation_memory` | 對話記憶 | 1 個 session + N 個 note 節點 | 對話結束時建立 |

### 7.4 具體實作

```python
# 初始化
from hyperdb import HypergraphDB

HG = HypergraphDB()

# ── Vertex ──────────────────────────────────────────

HG.add_v("note:research/HG-03", {
    "title": "超圖完整技術調研",
    "tags": ["hypergraph", "memory-system", "technical"],
    "content_hash": "abc123",
    "embedding_id": "emb_001"  # 對應外部向量庫
})

HG.add_v("person:Ryan", {
    "name": "Ryan",
    "role": "user",
    "description": "創業者，前 Momotoy 員工",
    "preferences": "繁體中文、懶惰、不愛重複操作"
})

HG.add_v("person:Emily", {
    "name": "Emily",
    "role": "partner",
    "description": "Ryan 女友，時尚"
})

HG.add_v("skill:hypergraph-skill", {
    "name": "hypergraph-skill",
    "category": "research",
    "description": "超圖主題研究 skill"
})

# ── Hyperedge ────────────────────────────────────────

# 主題聚合超邊（3元）：Ryan 研究超圖 + Emily 相關 + 技能開發
HG.add_e((
    "person:Ryan",
    "note:research/HG-03",
    "skill:hypergraph-skill"
), {
    "type": "topic_cluster",
    "description": "Ryan 主導的超圖技能開發專案",
    "created_by": "llm_merge",
    "confidence": 0.92
})

# 人物上下文超邊（2元）
HG.add_e((
    "person:Ryan",
    "person:Emily"
), {
    "type": "person_context",
    "description": "Ryan 和 Emily 的關係",
    "label": "戀人",
    "created_by": "manual"
})

# ── 檢索流程 ──────────────────────────────────────────

# Step 1: 向量檢索找到 top-k 節點
# → 用 Jina embedding 在外部向量庫找相關 note/person/topic

# Step 2: 雙向擴展
# retrieved_nodes → 找這些節點的 nbr_e_of_v() 超邊
# 超邊成員 → 再找這些成員節點的 nbr_v() 鄰居

def expand_via_hypergraph(db, retrieved_nodes, max_depth=2):
    frontier = set(retrieved_nodes)
    visited = set()
    results = set(retrieved_nodes)
    
    for _ in range(max_depth):
        for v in frontier:
            if v in visited:
                continue
            visited.add(v)
            # 找 v 的所有超邊
            for he in db.nbr_e_of_v(v):
                # 把超邊的所有成員節點加入結果
                for member in he:
                    if member != v:
                        results.add(member)
                frontier.add(member)
    
    return results - set(retrieved_nodes)  # 返回擴展的新節點
```

### 7.5 Obsidian 整合方案

```
Obsidian Vault
     │
     │  (新增超圖節點時)
     ▼
┌─────────────────────────────┐
│  Obsidian Note               │
│  ─────────────               │
│  title: HG-03 超圖技術調研   │
│  tags: [hypergraph, memory] │
│  links: [[person/Ryan]]     │
└──────────────┬──────────────┘
               │
               │ 同步觸發
               ▼
┌─────────────────────────────┐
│  Hypergraph-DB               │
│  ──────────────             │
│  V: note:HG-03 (attrs)      │
│  E: topic_cluster(...)      │
└──────────────┬──────────────┘
               │
               │ 向量化
               ▼
┌─────────────────────────────┐
│  Jina Embedding (oMLX)      │
│  ──────────────────          │
│  emb_001 → note:HG-03       │
└─────────────────────────────┘
```

### 7.6 實現順序

```
Phase 1（MVP）：直接可驗證
  1. Hypergraph-DB 初始化腳本
  2. 手動建立示範頂點/超邊（Ryan/Emily/Hermes/技能）
  3. 驗證 n-ary 超邊查詢正確

Phase 2（整合向量檢索）：
  4. 對接 oMLX Jina embedding
  5. 實現基於 embedding 的 top-k 檢索
  6. 實現雙向超圖擴展

Phase 3（Obsidian 自動化）：
  7. 讀取 Obsidian vault 中 note 的 tags/links
  8. 自動建立對應頂點
  9. 實現 LLM Merging（定期主題聚合）

Phase 4（完整 HGMEM）：
  10. 實現 Update/Insertion/Merging 演化操作
  11. 對齊 HyperGraphRAG 的雙向檢索策略
```

---

## 八、技術路線驗證清單

| 項目 | 狀態 | 備註 |
|------|------|------|
| Hypergraph 數學理論 | ✅ 完成 | 定義、矩陣、類型分類完整 |
| HGNN 神經網絡框架 | ✅ 完成 | 2018-2025 多個模型確認 |
| Hypergraph-DB 安裝 | ✅ 完成 | 0.3.0，uv + Python 3.11 |
| Hypergraph-DB API 實測 | ✅ 完成 | n-ary 超邊、持久化驗證成功 |
| HGMEM/MemGPT/HyperGraphRAG | ✅ 完成 | 三大記憶應用確認 |
| Ryan 系統缺口評估 | ✅ 完成 | 見第七節 Schema |
| oMLX Jina embedding 整合 | ⏳ 待驗證 | 需要 port 8140 |
| Obsidian note 導出介面 | ⏳ 待驗證 | 需確認 vault 讀取方式 |
| Schema MVP 實現 | ⏳ 待驗證 | Phase 1-3 分步 |

**技術路線封閉評估：**
- ✅ 超圖數學理論清晰
- ✅ 數據庫方案確認（Hypergraph-DB）
- ✅ 應用框架確認（HGMEM + HyperGraphRAG）
- ✅ 與現有架構整合可行
- ⏳ 待：實際 MVP 驗證

---

## 九、標籤

#hypergraph #memory-system #AI-agent #HGNN #technical-research
