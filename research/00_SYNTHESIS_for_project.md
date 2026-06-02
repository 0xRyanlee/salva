# Salva 研究綜述 — 對「精簡工具」真正有益的部分

> 來源:`vault/60_中文資料/指導文件/` + `vault/research/`(已複製進 `research/sources/`)。
> 目的:從 ryan 多年的設計與研究中,抽出**對一個乾淨、可測試、能用的 Salva 真正有益**的部分,
> 其餘野心明確封存。本文是 archive 分支的結論層;main 將據此做小做扎實。

---

## 一句話定性

合法、能商用、對自己與 agent 真有用的那部分 Salva,本質是:
**一個自架的「多輪語義檢索聚合 runtime」——關鍵詞圖驅動的查詢擴展 + 多 provider 檢索 + 去重清洗 + rerank + 結構化證據輸出。**

真正有護城河的兩個方向(強實體解析、深層背調)經 ryan 自己判斷:多屬 OSINT 灰區,合規後價值塌縮。**故不納入精簡核心。**

---

## 已入袋的學習(不需再建,留作知識)

這個項目作為學習載體**已經成功**。以下成果與工具是否上線無關,已是 ryan 的知識資產:

- 超圖理論(HGNN、超圖信號處理、n-ary 關係)— `research/sources/hypergraph/`
- RAG 演化譜系(Chunk → GraphRAG → LightRAG → OKH-RAG)— `Research_Report_Hypergraph_Memory_2026`
- Agent 記憶架構(HGMEM/MemGPT/LangGraph/HyperMem)— HG-01/04/07
- 檢索技術全景(IR、布林、Dorking、相關性回饋)— `keyword-graph-and-retrieval-techniques`

---

## 對精簡工具真正有益的 5 件事(全部來自 ryan 自己的文件)

### 1. 「最簡單實作架構」迴路 — 這就是 main 的藍圖
出自 `keyword-graph-and-retrieval-techniques.md` §9-10。ryan 早已畫好精簡版,只是被後來的平台腳手架埋掉:

```
單一關鍵詞 → 語義拆解(同義/近義/關聯/變體/組合) → 候選詞池
  → 搜索採樣 → 命中分析 → 六維加權 → 閾值剪枝 → 下一輪擴展
  → 核心關鍵詞簇 → 高價值 Query → 關鍵線索入口
```

### 2. 正確的加權回饋(共現 / 轉化 / 語義)— 修「空殼」的關鍵
ryan 文件裡的六維加權:**頻次、共現、轉化、來源、區域、語義距離**。
當前代碼(`core/keyword_graph.py:apply_telemetry`)**只重排已存在的 query token**,
缺了從檢索內容回灌新詞、缺共現/轉化/語義加權 —— 這正是 benchmark 實測 `memory_seeds_used=0`、
跨 run 不進步的根因。把這六維補上,「複利」才真的成立。

### 3. 檢索棧決策(已研究定案)
- 向量:**Jina embedding(native,非經 oMLX)** — ryan 最新決策,更新了 HG-06 的舊結論(oMLX-Jina)
- 混合檢索:**BM25 + vector,α≈0.5**(`A2_Hybrid_Search`、`E3`)
- Rerank:**BGE-Reranker,top-k 10→3**(`E2_Rerank_Models_Benchmark`)
- 向量存儲:LanceDB 或 sqlite-vec(輕量本地優先;`A1_Elasticsearch_vs_LanceDB`)

### 4. Dorking / Boolean / 進階運算符 + 反向(反義)
`keyword-graph-and-retrieval-techniques.md` 七、八節 + V2 的 dive 策略。
「反向 dorking / 反義詞排除」對應超圖設計裡的**負向關聯**——在精簡版裡可降級為
negative-keyword 與排除運算符,不需要超圖也能拿到大部分收益。

### 5. 7 階段管線的「模組邊界」(作為切分參考,非全做)
`7-stage-bd-pipeline-spec.md`:目標定義 → 關鍵詞生成 → 搜索採集 → 抓取提取 →
清洗去重打分 → 記憶強化 →(輸出)。精簡版保留前五段即是完整可用工具;第六段(記憶)
是第 2 點的加權回饋,做對即可,不需要 Hypergraph-DB。

---

## 明確封存的野心(不進 main)

| 野心 | 出處 | 為何封存 |
|---|---|---|
| Hypergraph-first **Agent OS**(整合 Piper/Handy/GenericAgent/Obsidian) | HG-06、HG-07 | 比 Salva 大一個量級,是另一個項目;Salva 只是其中檢索組件 |
| OSINT 深層背調 / 員工郵箱枚舉 | `osint-enrichment-master-plan`、Pirate 策略 | 合規/法律天花板,ryan 已判斷商用後價值塌縮 |
| HGNN / OKH-RAG / 超圖記憶演化 | HG 全系列 | research-grade,需團隊與論文級投入;留作學習 |
| 多租戶 / quota / SaaS 前台 | repo `apps/api`、`Front page concepts of api Saas` | 商業環境未成熟;在核心驗證前是維護負債 |
| 真超圖後端(Hypergraph-DB) | HG-03/06 | 精簡版用結構化 + 向量即可;超圖是未來事 |

---

## 範圍分叉(回答 ryan「我不知道邊界」)

不用現在決定 Salva 是否要長成整個知識庫記憶層。先把分叉釘清楚:

- **`main`** = 精簡發現工具(上面五點),乾淨、合法、可測試驗證、自己天天能用。
- **`archive/v1-and-research`(本分支)** = 當前完整版 + 全部研究與野心,完整保存,不丟。
- **Agent-OS 願景(HG-06/07)** = 未來若要,另起 repo / 階段,以 Salva 的穩定契約為基礎。

「Salva 要不要成為知識庫記憶層」這個問題,等精簡版用起來後自然會有答案。

---

## main 的下一步(僅記錄方向,本次不動 main)

1. 用 **native Jina embedding** 取代 `salva_core/vector_backends.py` 的 hash 偽向量。
2. 在 `retrieval/` 接 **BM25 + vector hybrid + BGE rerank**。
3. 修 `apply_telemetry`:加入**共現/轉化/語義**加權與內容詞回灌(讓複利真的發生)。
4. 砍/封存:多租戶、quota、超圖後端評估面、OSINT 的非合規路徑。
5. 用 `benchmark/` 當回歸守門,確認每步「真的更有效」。
