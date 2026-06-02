# 超圖 Hypergraph 關鍵詞擴展矩陣

**Date:** 2026-04-18
**Status:** Completed

---

## 一、數學理論（Mathematical Theory）

| 關鍵詞 | 說明 |
|--------|------|
| hypergraph | 超圖基本定義 |
| hyperedge | 超邊（連接任意數量節點的邊）|
| undirected/directed hypergraph | 無向/有向超圖 |
| incidence matrix | 關聯矩陣 |
| dual hypergraph | 對偶超圖 |
| Berge hypergraph | Berge 超圖 |
| balanced hypergraph | 平衡超圖 |
| totally balanced hypergraph | 完全平衡超圖 |
| alpha-regular hypergraph | α-正則超圖 |
| Hedgehog hypergraph | Hedgehog 超圖（Berge-Fulkerson猜想相關）|
| k-uniform hypergraph | k-均勻超圖（所有超邊大小為k）|
| Ramsey number | Ramsey 數（超圖推廣）|
| transversal hypergraph | 橫貫超圖 |
| hypergraph coloring | 超圖著色 |
| vertex coloring / edge coloring | 點著色 / 邊著色 |
| chromatic index | 著色指數 |
| hypergraph partition | 超圖分割 |
| Berge-Fulkerson conjecture | Berge-Fulkerson 猜想（組合學未解問題）|
| Hamilton cycle in hypergraphs | 超圖中的哈密頓圈 |
| Erdős–Ko–Rado theorem | EKR 定理（集合交叉理論）|
| transversal number | 橫貫數 |
| Helly property | Helly 性質（幾何/組合）|

---

## 二、數學結構（Mathematical Structures）

| 關鍵詞 | 說明 |
|--------|------|
| hypergraph Laplacian | 超圖拉普拉斯矩陣 |
| spectral clustering | 譜聚類（超圖推廣）|
| Cheeger inequality | Cheeger 不等式（高階推廣）|
| p-Laplacian | p-拉普拉斯算子 |
| hypergraph cut | 超圖割（分割代價）|
| conductance | 電導（圖/超圖分割質量）|
| higher-order Cheeger inequality | 高階 Cheeger 不等式 |
| normalized cut | 歸一化割 |
| balanced hypergraph partition | 均衡超圖分割 |
| k-clustering | k-聚類 |
| connected components | 連通分量 |
| hypergraph matching | 超圖匹配 |
| hypergraph isomorphism | 超圖同構 |

---

## 三、計算機科學應用（CS Applications）

| 關鍵詞 | 說明 |
|--------|------|
| hypergraph neural network (HGNN) | 超圖神經網絡 |
| message passing neural networks (MPNN) | 消息傳遞神經網絡 |
| edge-dependent vertex weights (EDVW) | 邊依賴節點權重 |
| hypergraph partitioning | 超圖分割（VLSI晶片設計）|
| hypergraph spectral clustering | 超圖譜聚類 |
| hypergraph matching | 超圖匹配（電腦視覺）|
| combinatorial optimization | 組合優化 |
| database many-to-many relationships | 數據庫多對多關係 |
| scene graph | 場景圖（電腦視覺）|
| knowledge hypergraph | 知識超圖 |
| knowledge graph embedding | 知識圖譜嵌入 |
| ontology learning | 本體學習 |
| GraphRAG | 圖檢索增強生成 |
| TF-HNN (training-free hypergraph neural network) | 無訓練超圖神經網絡（arxiv 2310.07684）|

---

## 四、交叉應用領域（Cross-Domain Applications）

| 領域 | 關鍵詞 |
|------|--------|
| **生物信息學** | protein complex / gene regulatory network / protein interaction network |
| **社交網絡** | multi-way interaction / group communication / collaboration network |
| **推薦系統** | knowledge-aware recommendation / session-based recommendation |
| **電腦視覺** | scene understanding / object relationships / image segmentation |
| **晶片設計** | VLSI hypergraph partitioning / circuit testing |
| **藥物發現** | drug-target interaction / molecule hypergraph |
| **知識管理** | ontology learning / personal knowledge base / semantic search |
| **交通網絡** | road network / multi-modal transport |
| **神經科學** | brain connectivity / neural network topology |

---

## 五、頂級資源（Top Resources）

### 論文

| arXiv ID | 標題 |
|----------|------|
| arXiv:2602.05665 | Graph-based Agent Memory: Taxonomy, Techniques, and Applications |
| arXiv:2303.15356 | Hypergraphx: a library for higher-order network analysis |
| arXiv:2310.07684 | TF-HNN: Training-Free Hypergraph Neural Networks |
| arXiv:2203.16995 | Message Passing Neural Networks |
| arXiv:2305.18256 | HyNT: Hyper-Relational Knowledge Graph Representation Learning |
| OpenReview:coF6roWi9M | HGMEM: Hypergraph-Based Memory for Multi-Step RAG (ICLR 2026) |
| ACM Surveys 2022 | A Survey on Hypergraph Representation Learning |

### 工具庫

| 名稱 | 說明 |
|------|------|
| **HypergraphX (HGX)** | Python 超圖分析庫（https://pypi.org/project/hypergraphx/）|
| **NetworkX** | Python 圖論庫（可視化超圖）|
| **PyAMG** | 代數多重網格（超圖拉普拉斯求解）|

### 網站

| 名稱 | 說明 |
|------|------|
| Wikipedia: Hypergraph | 超圖基本定義和數學背景 |
| TutorialsPoint | 超圖類型分類完整教程 |
| Onto-KIT | 地球觀測數據本體整合工具 |

---

## 六、oMLX / 本地模型（Local Models）

### VLM 可用於 Vision Hypergraph 視覺化

| 模型 | 說明 |
|------|------|
| Qwen2-VL | 阿里開源多模態（oMLX 可用但未裝）|
| Qwen2.5-VL | 升級版 |
| GLM-4V | 智譜多模態 |
| Pixtral | Mistral 多模態 |
| LLaMA-3.2-Vision | Meta 多模態 |

**注意：** oMLX 目前只有 3 個純文字模型（gemma-4-e2b-it / jina-embeddings-v5 / jina-reranker-v3），無 VLM。

---

## 七、Hypedia（超圖+百科）

| 關鍵詞 | 說明 |
|--------|------|
| hypergraph database | NoSQL 超圖數據庫（HyperDB）|
| RDBMS → NoSQL hypergraph migration | 關係型→超圖遷移 |
| schema transformation hypergraph | 模式轉換（Springer's 2023 論文）|
| Query-based denormalization (QBDNH) | 基於查詢的非規範化 |

---

## 下一步行動

- [ ] 確認 Obsidian vault 的 `memory/topics/` schema 規範
- [ ] 設計第一個超圖主題 note（如 HG-03_Hypergraph_Fundamentals.md）
- [ ] 測試 HypergraphX 庫
- [ ] 設計 hypergraph skill（工具 workflow）

---

## 標籤

#hypergraph #keywords #research #math #computer-science
