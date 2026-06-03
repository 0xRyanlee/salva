# Salva 研究與設計檔案庫(archive 分支)

本目錄是 ryan 的 Obsidian vault 中所有 Salva 相關文章的**整理、歸納與分類**。
高訊號的源文件已複製進 `sources/`(讓本分支自含知識,不依賴 iCloud);
重複或離題的只在下表登錄處置與原始位置,vault 原文保留不動。

- **提煉結論見 [`00_SYNTHESIS_for_project.md`](00_SYNTHESIS_for_project.md)** —— 對精簡工具真正有益的部分。
- **戰略討論與決策記錄見 [`01_DISCUSSION_AND_DECISIONS.md`](01_DISCUSSION_AND_DECISIONS.md)** —— 八維分析、競品全景、多輪收束、超圖架構裁決、prove-first 實驗。
- 原始 vault 路徑前綴:`~/Library/Mobile Documents/iCloud~md~obsidian/Documents/workspace/`

處置定義:
- **KEEP** — 對項目有益,已複製進 `sources/`
- **REF** — 自動生成的研究摘要,原創性低但含棧決策與來源連結,複製作參考
- **DUP** — 與 repo `README/docs/` 重複,已被取代,不複製(repo 為準)
- **SCOPE** — 屬更大的 Agent-OS / OSINT / SaaS 野心,**封存**,不進 main
- **ADJACENT** — 相鄰的 agent 子系統(非 Salva 核心),封存

---

## 設計文件(指導文件/)

| 處置 | 文件 | 閱讀深度 | 價值 / 去處 |
|---|---|---|---|
| KEEP | Techeniques of search for leads | 深讀 | 檢索理論+方法全集;**§9-10 即精簡藍圖**。→ `sources/design/keyword-graph-and-retrieval-techniques.md` |
| KEEP | 自動化 BD Leads 系統:7 流程架構規格 | 讀結構 | 7 階段管線 + Jina/LanceDB 參與點。→ `sources/design/7-stage-bd-pipeline-spec.md` |
| KEEP | SALVA_V2_ARCHITECTURE_REVIEW | 全讀 | 5 層目標架構 + 成功標準。→ `sources/design/v2-architecture-review.md` |
| KEEP | Salva Runtime architecture notes | 全讀 | 簡短架構備註。→ `sources/design/architecture-notes.md` |
| SCOPE | Salva_OSINT_Enrichment_Master_Plan | 讀結構 | OSINT 深背調,合規天花板,封存。→ `sources/design/osint-enrichment-master-plan.md` |
| SCOPE | Front page concepts of api Saas for salva | 標題 | SaaS 前台,商業環境未成熟,封存(vault 保留) |
| DUP | Salva Runtime README | 標題 | 已被 repo `README.md` 取代 |
| DUP | Salva Runtime Skill Guide | 標題 | 已被 repo `SKILL.md` / `docs/` 取代 |
| DUP | Salva Runtime TODO | 標題 | 已被 repo `TODO.md` 取代 |
| DUP | Salva Runtime 功能總覽與路線圖 | 標題 | 已在 repo `docs/` |
| DUP | Salva Runtime 多Provider檢索與部署設計 | 標題 | 已在 repo `docs/` |
| DUP | Salva Runtime 封裝與分發路線圖 | 標題 | 已在 repo `docs/` |
| DUP | Salva Runtime 使用者體驗與成熟度審計 | 標題 | 已在 repo `docs/` |
| ADJACENT | Piper - empower the low-Bs | 標題 | Agent-OS 意圖層,封存 |
| ADJACENT | Handy - Slowly make agents smarter | 標題 | Agent-OS 反饋層,封存 |
| ADJACENT | Memory optmization thoughts | 標題 | Agent-OS 記憶分層,封存 |
| ADJACENT | Waker - Event-Driven Agent Wake System | 標題 | 事件喚醒系統,離題,封存 |
| ADJACENT | Gateway Restart Recovery Policy | 標題 | 運維策略,離題,封存 |

> `指導文件/Archive/` 8 份(Salva Skill 各版本、OpenClaw OS、全球開發手冊等)— ryan 已自行歸檔,留在 vault 原處不動。

---

## 超圖系列(research/02_HG_Series/)— 全部 KEEP 作學習/參考

複製至 `sources/hypergraph/`。HG-06 是 ryan 的**整合結論**(外源研究×內源設計),但其範圍是
「Hypergraph-first Agent OS」,大於精簡 Salva。HG-07 擴展理論框架。其餘為論文綜述與技術調研。

| 文件 | 內容 |
|---|---|
| Research_Report_Hypergraph_Memory_2026 | 文獻地圖 + 5 層架構 + OKH-RAG 檢索流程(深讀 3、4 部) |
| HG-03_Hypergraph_Comprehensive_Research | 超圖數學/HGNN/DB 對比 + 技術棧 + Schema(深讀六節) |
| HG-06_Integrated_Architecture_Design | **整合結論**:統一棧、Flow 6 具體化、MVP 方案(深讀) |
| HG-07_HyperMem_Validation... | 理論框架擴展(Episode/矛盾檢測/記憶蒸發)|
| HG-00/01/02/04/05/0A/0B | vault 索引、論文綜述、關鍵詞超圖、記憶綜述、代碼分析等(標題級) |

---

## 自動生成研究(research/03_Research_2026-03-21/)— REF

複製至 `sources/auto-generated/`。模板式研究摘要(標題含 "implementation example"),
原創性低,**價值在棧決策與來源連結**:

- `A1_Elasticsearch_vs_LanceDB`、`A2_Hybrid_Search`、`A3_SearXNG_Deployment` — 檢索棧
- `E1_Embedding_Models_Comparison`、`E2_Rerank_Models_Benchmark`、`E3_Graph_Based_Retrieval` — 向量/rerank 棧
- `B1_Keyword_Research`、`B2_AEO_LLM_Optimization` — 關鍵詞
- `C/D/F/X` 系列 — Agent skill / plugin / RAG framework 參考(多屬 Agent-OS 範圍)

---

## 一句話

ryan 的設計與研究**遠比代碼完整**;精簡 Salva 不缺設計,缺的是「把已設計好的精簡迴路扎實實作、
其餘野心封存」。提煉見 `00_SYNTHESIS_for_project.md`。
