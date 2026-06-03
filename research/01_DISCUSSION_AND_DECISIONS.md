# Salva 戰略討論與決策記錄(2026-06-03)

> 一次多輪討論的完整分類收錄。承接 [`00_SYNTHESIS_for_project.md`](00_SYNTHESIS_for_project.md)。
> 性質:決策日誌 + 競品研究 + 架構裁決。不是規格(規格見未來 `docs/spec/`)。

---

## 0. 當前決策狀態(TL;DR)

| 維度 | 決定 |
|---|---|
| **身份** | 結構化發現 = Perplexica 的 agent 對應物(回 entity/relation/evidence,不回 prose) |
| **Beachhead** | 商業實體情報:公司 + 股權穿透 + 主體關係圖譜 + 法律/招聘/業務/融資/新聞多源聚合 |
| **生態關係** | 獲取層 + 互通:輸出 FtM 相容、實體解析接 Nomenklatura/Yente,不重造、不打資料戰 |
| **核心差異化** | typed n-ary 超圖(role + arity + evidence)做語義穿透與呈現,勝過 FtM 二元 reified |
| **架構立場** | incidence model / HIF 交換 / role-arity-evidence schema / projection-first(同意);TypeDB·Rust·HGML 延後 |
| **下一步** | **prove-first 最小實驗**:用最小 stack 證明「超圖穿透是否真的更有效」 |
| **身份張力(未決)** | 個人工具/學習 vs 試圖做生意 —— 尚未明選,先實踐再說 |

---

## 1. 起點:審計與「空殼」診斷

- repo 自稱 72/72 完成、README 稱「v1 完成」,但 `pytest` 實測 25 failed(22 整合無 skip guard + 3 過時單元測試,已修)。
- **核心診斷:骨架 ~80%(端點/persistence/schema/分層/MCP/CLI/SDK),智能核心 ~15-20%(空殼)。**
- benchmark 實證:跨 run 複利記憶是**套套邏輯**——`source_nodes` 只存靜態 vocab 衍生詞,`seed_from_memory` 灌回本來就有這些詞的圖 → `memory_seeds_used` 恆 0,run K ≡ run 1。`apply_telemetry` 只重排已存在的 query token,**從不從內容學新詞**。
- 詳見記憶 [[audit-baseline-20260603]]、[[project-vision-and-hollow-core]]。

---

## 2. 戰略八維分析(精簡核心)

- **Kano**:已建的全是基本型(商品化)或無差異型(負債);魅力型(複利、結構化輸出、反向擴展)全是空殼。資源配置與價值曲線錯位。
- **市場**:agent 檢索分五層(託管 API / 自架 AI 搜尋 / OSS RAG / 深研究 / Lead-OSINT);Salva 原落在「自架 + agent-native + 結構化發現」的空隙。
- **競品**:最接近 = Perplexica(33k★,但人用 Q&A、無結構化 entity、無複利)。
- **SWOT**:S=乾淨分層/可注入 vocab/證據鏈/自架/創辦人檢索深度;W=差異化空殼/臃腫/無真 embedding/單人/零用戶/護城河踩 OSINT;O=結構化發現空白 niche/MCP 生態/瀏覽器人用面;T=託管 API 免費額度商品化/OSS 擴張/法律灰區。
- **可行性**:技術高(棧現成);資源僅在「精簡 + 適度複利」範圍可行;商業近期低。
- **技術路線**:native Jina + BM25 hybrid(α≈0.5)+ BGE rerank(10→3)+ LanceDB/sqlite-vec + 關鍵詞圖,與業界一致;唯一研究風險是複利回饋。
- **完成度**:廣度高、深度空;誠實估精簡工具 ≈ 40-50%。
- **開源對比**:無任何 OSS 精準等於「自架 agent-native 結構化發現 + 複利」——既是機會也是警訊。

---

## 3. 競品全景(校準後)

**通用 agent 檢索**
- 託管 API:Tavily、Exa、Firecrawl、Linkup、Brave Search API、Serper、Jina、Parallel
- 自架 AI 搜尋:**Perplexica**(SearXNG + rerank + 引用答案)、SearXNG(245 引擎 meta-search)
- OSS RAG:RAGFlow、LightRAG(HKUDS)、txtai、Haystack
- 深研究 agent:GPT Researcher、LangChain open_deep_research
- OSINT:SpiderFoot(200+ 模組)、theHarvester、Amass、Maltego

**商業實體情報(beachhead 確定後的真實競品)**
- 開源棧:**FollowTheMoney(FtM)**(實體+關係圖資料模型,4.0/2025)、**Aleph**(OCCRP 調查平台)、**OpenSanctions**、**Yente**(實體匹配 API)、**Nomenklatura**(跨源實體整合 + lineage)、Rigour、Zavod
- 商業:**Sayari**(15 億實體、250+ 法域、受益所有權圖、AI 實體解析)、**OpenCorporates**(2 億公司、140+ 法域、公開登記)、天眼查/企查查(中國)、Diffbot、Veridion

**深研發現(WebFetch OpenSanctions 實體結構)**:
- FtM 關係是 **reified entity**(Ownership 有 owner/asset/percentage/startDate),但**本質仍二元**(兩端);多方結構靠串接多條二元邊。
- 文件**明說複雜多方結構超出核心模型範圍**,要外接 Neo4j/Gephi/RDF —— **這就是缺口**。
- 實體解析已開源可重用;FtM 方向是「調查型知識圖譜 community + Python 清洗對齊棧」,不做獲取/表示創新。

---

## 4. 多輪收束(決策鏈)

- **R1 身份**:接受「結構化發現 = Perplexica 的 agent 對應物」,去建差異化。差異化拆兩塊:(A) 結構化輸出(易,立即區隔)/(B) 複利查詢智能(難,長期護城河)。建議先 A。
- **R2 Beachhead**:選 1+2 = **商業實體情報**(公司+股權穿透+主體關係圖譜+多維聚合)。→ 救活超圖(n-ary=超邊)、合法乾淨、需求已證明、硬問題從「複利」變「實體解析」。
- **R3 生態**:選「獲取層 + 互通」,且「先 4 再 1」(先深研生態再定接法)。
- **超圖論點裁決**:n-ary 忠實度**成立但 incremental**(FtM+Neo4j 已能穿透);最佳形態 = 疊在 FtM 上(import/export FtM + 借實體解析 + 對內超邊表示 + 超圖檢索)。
- **R4 疑慮**:浮出真正關切 = **超圖架構的實現邏輯**(非市場/可行性)。

---

## 5. 超圖架構裁決

**同意(對的)**
- **incidence model 作主儲存**——關鍵 reframe:incidence 結構在數學上**就是**超圖,不是 property graph 假裝。多跳穿透 = recursive CTE。
- **HIF 作交換格式**——便宜、前瞻、與 XGI/HyperNetX 互通。
- **role typing + arity constraint + evidence binding 的 schema**——整套的金子,正是 FtM 二元模型所缺。
- **Canonical → many projections;明文層(HGML)當投影不當真相**。

**延後/不同意**
- **TypeDB 當核心 → 延後**。概念最貼但 3.x 生態震盪、運維重、鎖定風險;且 TypeDB relation 與 incidence table **本質同構**(都是 reified n-ary)。MVP 不需 TypeQL 級推理。先 SQLite/Postgres-incidence,TypeDB 之後可選。(注:用戶自己 MVP 清單也是 Postgres-main/TypeDB-optional。)
- **「HyperNetX 太重 → Rust/Cytoscape 重寫計算」→ 不同意**。Cytoscape.js 是**視覺化**非計算(類別錯);Rust 重寫**過早**。MVP compute 用 SQL/Python;HyperNetX 只離線分析;cy 留給觀察窗口。
- **現在發明 HGML → 延後**。先用 HIF + YAML;HGML 當人類投影,等核心跑通再做。

**最大 meta 風險**:infra-first/tooling-first(選 TypeDB、Rust 重寫、設計 HGML、三視圖、八投影,在核心被真實資料證明之前)= **生出當前臃腫 Salva 的同一個模式**。架構是對的**終點**,不是**起點**。

**落到 Salva**:這是把現有 `Hold`(已有 hyperedge)升級成 typed-n-ary incidence store——**延續,非重做**。

---

## 6. 決定的方向:prove-first 最小實驗

> 「先實踐,測試看是否真的更有效」。

**實驗規格(最小 stack,單人可做)**
1. **SQLite** incidence 三表(nodes / hyperedges / incidences: edge_id, node_id, role, order_index, props),帶 evidence 綁定。
2. 挑 **2-3 家有多層股權的真實公開公司**;Salva 獲取層多源(新聞/登記/filings)抽出實體 + 股權事實 + 證據。
3. 用 **n-ary 超邊**表示(roles + arity + evidence)。
4. **Python recursive 穿透**(2 跳:誰終極控制)+ 一張 **bipartite/star 投影**(靜態圖或 cy)。
5. **對照組**:同資料用 FtM 二元圖,**展示語義差異**。
6. **export HIF** 證互通。

**驗收標準**:「typed n-ary 超圖穿透 + role/arity/evidence」相較 FtM 二元,**在穿透完整性與呈現語義上是否真的更有效**——可展示、可說清差在哪。若差異 marginal,beachhead/差異化要重估。

**前置探針(可能更先)**:疑慮 B(資料來源死穴)——公開網路能否可靠拿到股權事實。拿得到,實驗才有料。

---

## 7. 封存的野心 / 範圍邊界(終點非起點)

| 封存項 | 出處 | 為何不是起點 |
|---|---|---|
| Hypergraph-first Agent OS(Piper/Handy/GenericAgent) | HG-06/07 | 比 Salva 大一級,另一個項目 |
| OSINT 深背調 / 員工郵箱枚舉 | OSINT plan、Pirate | 法律灰區,合規後價值塌縮 |
| TypeDB / Rust 計算 / HGML / 三視圖 / 八投影 | 本次架構討論 | infra-first;證明論點後再長 |
| 多租戶 / quota / SaaS | repo apps/api | 商業未熟,核心未驗前是負債 |

---

## 8. 來源(web research,2026-06)

- Agent search APIs: [aimultiple](https://aimultiple.com/agentic-search)、[firecrawl best web search APIs](https://www.firecrawl.dev/blog/best-web-search-apis)
- OSS RAG / deep research: [RAGFlow](https://github.com/infiniflow/ragflow)、[GPT Researcher](https://github.com/assafelovic/gpt-researcher)、[LangChain open_deep_research](https://github.com/langchain-ai/open_deep_research)、[firecrawl best OSS RAG](https://www.firecrawl.dev/blog/best-open-source-rag-frameworks)
- 自架 AI 搜尋:[Perplexica self-host](https://ossalt.com/guides/how-to-self-host-perplexica-open-source-perplexity-2026)、[SpiderFoot](https://github.com/smicallef/spiderfoot)
- 商業實體情報 / FtM:[OpenSanctions entities](https://www.opensanctions.org/docs/entities/)、[FtM (Aleph docs)](https://docs.aleph.occrp.org/developers/explanation/followthemoney/)、[FtM 4.0](https://www.opensanctions.org/articles/2025-07-13-followthemoney/)、[Sayari Graph](https://sayari.com/platform/graph/)、[OpenCorporates KG](https://blog.opencorporates.com/2025/10/01/legal-entity-knowledge-graphs/)
