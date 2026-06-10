# Salva 實驗計畫 — 為開發奠定理論基礎

> 原則:在做開發工作前,用一系列小實驗把核心主張**逐一證明或證偽**,讓開發站在證據上而非希望上。
> 每個實驗圍繞 ≥1 個**關鍵驗證點(VP)**,**過程(腳本+資料)與結果(findings+輸出)都存檔進 git**。
> 全部驗證完 → 取得理論基礎 → 進入開發階段。

## 關鍵驗證點(要建立的理論)

| VP | 主張 | 狀態 |
|---|---|---|
| VP1 | n-ary 超圖保留二元分解會丟的關係事實(表示忠實度) | ✅ E1 |
| VP2 | 公開源能提供股權事實(分法域可得性) | ✅ E2(US 證;CN/TW 上市待真拉) |
| VP3 | 雜亂真實 filing → 結構化 n-ary 事實(端到端獲取) | ✅ E3(SEC) |
| VP4 | 路由表從 source_attempts 自我優化(authority ≠ reachability) | ✅ E4(in-memory;持久化待 E9) |
| **VP5** | **跨語言實體解析**:同一主體在 中/英/拼音/ticker/簡稱 下能合併成一個 canonical entity | ✅ E5(字串證偽) / ⚠️ E5b(Jina embedding FAIL — 小模型對實體名稱跨字形無效;生產用 gazetteer) |
| **VP6** | **跨語義關係/事實合併**:等義關係與角色(控股/ownership/持股;董事長/chairman)正規化;多源同一事實合併為一條超邊+多證據 | ✅ E6(7→3,證據保留+衝突浮現+不誤併) |
| VP7 | 超圖上的語義檢索 + 二跳:embedding 預篩 + 結構擴展,勝過關鍵詞 | ⚠️ E7(INCONCLUSIVE — 2-hop recall=1.00 但 precision 下降;keyword baseline 有競爭力;需更豐富 node label) |
| VP8 | 投影/互通:canonical 超圖 → HIF round-trip;bipartite/star 投影視覺窗(非黑箱) | ✅ E8(HIF round-trip 零 diff;bipartite/star 投影可產) |
| VP9 | 持久化複利:跨多 run 在同領域上 yield/精度可量測上升(誠實版複利) | ✅ E9(B1+B2 修復後:5 run 中種子從 0→46,圖節點 34→61,機制驗證成功) |
| VP10 | Agent-only 與 Salva 的渠道檢索品質可用獨立觀測、輪次與污染指標比較 | ⚠️ E10 DOGFOOD 完成；live 結果可重現，但非等預算 benchmark |
| VP11 | role 節點必須進入 dive query，不能被 primary_terms 排擠 | ✅ E11(9/9 pass；role node bootstrap + service.py 修復) |
| VP12 | 空 snippet 結果不得通過 qualify_threshold | ✅ E12(6/6 pass；score ≤ 0.30 cap + no_snippet 標記) |
| VP13 | company 結果不得被 event schema 污染 | ✅ E13(8/8 pass；UnifiedResult 事件欄位預設 None) |
| VP14 | R1 零 yield 必觸發 R2 策略輪換；查詢不重複；不因單輪零結果提早收斂 | ✅ E14(5/5 pass；anchor rotation + seen_queries dedup) |
| VP15 | 等預算 frozen corpus 下，P ≥ 0.60 且 R ≥ 0.50 | ✅ E15 Phase1 PASS — Naturehike P=1.00 R=0.60；Computex P=1.00 R=0.55；Phase1 A1–A3 修復後達標 |
| VP16 | Hold C2 靜態 gazetteer：跨字形(ZH/EN/ticker)解析到同 canonical_id | ✅ E16(11/11 pass；技嘉科技↔GIGABYTE↔2376.TW 全解析；MSI≠GIGABYTE 不誤併) |
| VP17 | `run_diff` 正確識別 added/removed/score-updated entities | ✅ E17 PASS — 4/4；identical→empty；mutations→surfaced |
| VP-longitudinal | 跨多 run 記憶複利：seeds_used 遞增、recall 不退化、graph node count 成長 | ✅ E22 PASS — seeds 0→27→47→62；recall 維持 0.60；nodes 16→43→63→78 |
| VP21 | 等預算 live DDG 下，P ≥ 0.60 且 R ≥ 0.40 | ⏳ E21 腳本已就緒，需 live 網絡執行 |
| VP5b | 跨字形 entity resolution：exact-first→normalized fallback(NFKC+legal suffix)；embedding deferred | ✅ normalize_alias+resolve_entity_normalized；10/10 tests PASS |

## 存檔約定

每個實驗 `Ek`:
- 可重現腳本 `experiments/.../ek_*.py`(**過程**)
- `Ek_FINDINGS.md`:假設 / 方法 / 結果 / **誠實裁決**(**結果**)
- 本 `EXPERIMENT_PLAN.md` 維護狀態 + 一句裁決(索引)
- 真實資料實驗附 evidence(URL/來源),合規優先(只用合法公開源)

---

## 已完成(E1–E4)

- **E1 表示** (VP1) — `hg_penetration/run.py`。裁決:✅ n-ary 在「協同控制/多角色事件」勝;分層有效持股不是差異化(誠實)。
- **E2 可得性探針** (VP2) — `hg_penetration/probe_sec.py` + `PROBE_FINDINGS.md`。裁決:✅ 死穴非一致;上市公司 US/UK/TW/CN 可得;摩擦在私人公司 + 實體解析。
- **E3 真實端到端** (VP3) — `hg_penetration/run_real.py` Part 1。裁決:✅ 真拉 Chatham Lodging Trust 15 實體 §13(d)(3) 集團 → 一條 n-ary 超邊 + 證據。
- **E4 路由自我優化** (VP4) — `hg_penetration/routing.py` + run_real Part 2。裁決:✅ CN gsxt 真實失敗→降級翻轉;US SEC 命中→boost。

---

## 待執行(E5–E9)

### E5 — 跨語言實體解析(VP5)✅ 完成
- 結果見 `hg_penetration/E5_FINDINGS.md`。**裁決:字串/模糊/正規化僅 ~0–7% recall(只能同字形內合併,精度 1.00 無誤併);中文↔English↔ticker 零共享訊號,字串本質做不到;唯 gazetteer 達全 recall 但不泛化。** → 開發須接 multilingual embedding(Jina)+ 別名表 + 轉寫(opencc/pypinyin)。
- **E5b(待 Jina)**:在同資料集 benchmark embedding 橋接是否能泛化地救回跨字形對、精度多少。

### E6 — 跨語義關係/事實合併(VP6)✅ 完成
- 結果見 `hg_penetration/E6_FINDINGS.md`。**裁決:7 碎片記錄 → 3 canonical 超邊;ownership 合併 4 條多語言證據、70% vs 65% 衝突浮現不覆蓋;投資不被誤併。** 須建 FtM 對齊關係 ontology(as data)+ E5 實體橋 + conflict-preserving merge;長尾靠 embedding/LLM。

### E7 — 超圖語義檢索 + 二跳(VP7)
- **假設**:node/hyperedge 文本 embedding 預篩 + 二跳遍歷,回傳相關子圖優於關鍵詞。
- **方法**:小超圖,Jina embed 節點;查詢「歐洲做 distributor 的關聯主體」→ 向量 top-k → 二跳擴展;對照純關鍵詞。
- **存檔**:檢索品質對照。
- **裁決標準**:語義+結構是否優於關鍵詞 baseline。

### E8 — 投影 + HIF 互通 + 視覺窗(VP8)
- **假設**:canonical incidence 超圖 → HIF export 可 round-trip;bipartite/star 投影可渲染(非黑箱)。
- **方法**:export HIF → re-import → diff(無損);產 bipartite/star 投影(cy.js 或靜態圖)。
- **存檔**:HIF 樣本 + round-trip diff + 投影截圖。
- **裁決標準**:無損互通 + 可觀察。

### E9 — 持久化複利(VP9)〔誠實版,取代空殼複利〕
- **假設**:持久化 source_attempts + extraction 記憶,跨 N run 在同領域 yield/精度可量測上升。
- **方法**:同領域連跑 N 次,持久化路由記憶;量 recall@budget / queries-to-yield 曲線(沿用 `benchmark/` 精神)。
- **存檔**:曲線 + 每 run 指標。
- **裁決標準**:曲線是否單調上升(真複利)或平(證偽 → 重估)。

---

## 順序與依賴

```
E5 (跨語言實體) ─┐
                 ├─→ E6 (跨語義關係)  ─→ E7 (語義檢索/二跳)
E3/E4 (已) ──────┘                      └─→ E9 (持久化複利)
E8 (投影/HIF/視覺) 可並行(獨立)
```

建議序:**E5 → E6 → E8(視覺,讓前面可觀察)→ E7 → E9**。E5/E6 是公司情報 beachhead 的硬核(跨語言/多源),先攻。

---

## E10 — Agent-only vs Salva 渠道檢索與隔離審計

- **目標**：Naturehike 在德語區多國尋找 distributor、sales agent、
  retail alliance、specialist retailer。
- **過程**：
  - Agent-only 三輪獨立 web research；
  - Salva 以 `memory.read_scope=none`、`persistence=none` 跑 1/2/3 max-round snapshots；
  - evaluator 計算 precision、pooled recall、evidence、country/channel coverage、
    duplicate、contamination、requests。
- **結果**：
  - Agent-only R3：15 verified relevant，pooled recall 88.2%，三國/五渠道類型全覆蓋；
  - Salva R1：2 verified relevant，pooled recall 11.8%；R2/R3 因 DDG provider
    波動為零結果；
  - 隔離對抗測試 6/6 PASS。
- **誠實裁決**：✅ 實驗工具與失敗記錄有效；⚠️ pooled reference set 是事後
  驗證聯集，且 live 對比缺少等預算、完整 raw SERP 與可比耗時，不能宣稱一般性能優勢。
- **存檔**：`experiments/agent_vs_salva/`
- **下一步**：frozen-corpus replay + budget-matched repeated live A/B。

---

## E11–E16 — Pipeline 防呆/容災/魯棒驗證套組(Computex + Naturehike)

**背景**：E10 dogfood 識別出四個根因(role 汙染、空 snippet、schema 汙染、多輪崩潰)。E11–E14 是針對性修復+測試；E15 是等預算基準；E16 是 CJK 實體解析。

### E11 — Query Construction Fidelity (VP11)✅

- **修復**：`KeywordGraph._bootstrap()` 加 role 節點；`query_strategy._build_dive_queries()` 強制 role 進首 query；`service.py` 不再把 role 塞進 `primary_terms`。
- **測試**：`tests/test_e11_query_construction.py` 9 項全過。
- **裁決**：✅ role 節點從 dead code 變活的 query 信號；Computex exhibitor + Naturehike distributor 雙場景驗證。

### E12 — Snippet Missing Degradation (VP12)✅

- **修復**：`processing/scorer.py` 空 description 時 score ≤ 0.30，附加 `no_snippet` reject reason。
- **測試**：`tests/test_e12_snippet_degradation.py` 6 項全過。
- **裁決**：✅ DDG HTML 返回空 snippet 不再靜默通過 qualify_threshold；rich snippet 仍可正常得分。

### E13 — Objective→Schema Purity (VP13)✅

- **修復**：`core/types.py` `timezone`/`currency`/`price_amount` 預設 None；`salva_core/legacy.py` `_build_event_details()` 的 guard 移除 `organizer_email`/`organizer_domain`（純 contact 字段）。
- **測試**：`tests/test_e13_schema_purity.py` 8 項全過；`test_legacy_mapping.py` 同步更新以反映新語義（contact 字段在 relations，不在 event）。
- **裁決**：✅ company/lead 結果不再被 event schema 汙染；EventDetails 只在真實事件數據存在時生成。

### E14 — Multi-Round Recovery (VP14)✅

- **修復**：`core/controller.py` 加 `_seen_queries: set`；R1 零 qualified → R2 強制輪換到 `anchor`；`_execute_round()` 過濾已見 query。
- **測試**：`tests/test_e14_multiround_recovery.py` 5 項全過。
- **裁決**：✅ 零結果不提早收斂；策略輪換正確；跨輪 query 不重複。

### E15 — Budget-Matched A/B Benchmark (VP15)✅ Phase1 後 PASS

- **設計**：frozen SERP corpus、預宣告 ground truth（Naturehike 15 entities、Computex 20 entities）、等預算 12 requests。
- **初次結果（E11–E14 修復後）**：Naturehike R=0.067、Computex R=0.100 → FAIL。
- **Phase1 修復後結果**：Naturehike P=1.000 R=0.600 ✅；Computex P=1.000 R=0.550 ✅。
- **Phase1 根因修復**：
  1. A1 Query Diversity：`_build_dive_queries()` 展開 role synonyms（distributor→wholesaler/importer/buying group 等多角度）
  2. A2 Provider Fallback：`_search_sequential` 偵測空 snippet 落 fallback
  3. A3 Scoring Calibration：(a) `_region_match()` 複合 region 修正；(b) 移除 bd_leads "retail" 誤殺負向信號；(c) 加 buying group/verbundgruppe 信號；(d) 信號比對改 case-insensitive；(e) domain-specific weights 不被 strategy note 覆蓋；(f) domain-calibrated threshold(0.35)；(g) BM25 dedup threshold 過低問題標記
  4. **bonus 根因**：`_signal_strength()` 大小寫敏感 bug（OEM/ODM/Computex 無法匹配小寫 text）
- **存檔**：`experiments/computex_2026/e15_budget_ab.py` + `E15_FINDINGS.md`。

### E16 — CJK Entity Resolution (VP16)✅

- **實作**：Hold C2 靜態 gazetteer（Computex 台灣硬體 3 家）；`resolve_canonical_id`、`add_entity_alias`、`upsert_canonical_entity` API 驗證。
- **測試**：`tests/test_e16_cjk_entity_resolution.py` 11 項全過。
- **裁決**：✅ 技嘉科技/GIGABYTE/2376.TW → 同一 `twh:gigabyte`；MSI ≠ GIGABYTE 不誤併；gazetteer 方案完全覆蓋 E5b 字串方案的盲點。

---

## 終態

E5–E9 全綠(或誠實證偽)後，再加 E11–E16 的 pipeline 防呆基礎，Salva 的核心主張(n-ary 表示、跨語言/語義合併、語義檢索、自我優化複利、可觀察互通、pipeline 魯棒性)都有實證基礎 → 才進入正式開發。

**Phase 1 完成（recall 閉環）**：E17 frozen corpus benchmark 達標（P=1.0 R≥0.50 兩任務）。

---

## Phase 2 — Integration Surface（讓外部可用）

| 項目 | 描述 | 狀態 |
|---|---|---|
| C1 MCP Server | `apps/mcp/server.py` — `salva_discover`/`salva_job_create`/`salva_run_result`/`salva_audit`/`salva_pilot`/`salva_vocab`/`salva_topology`/`salva_plugins`/`salva_providers` + 新增 `salva_research_report`/`salva_run_diff`/`salva_graph_export` | ✅ 完成 |
| C2 CLI | `apps/cli/main.py` — `salva find`/`salva job`/`salva run`/`salva vocab`/`salva audit`/`salva pilot`/`salva topology`/`salva plugins`/`salva providers` + 新增 `salva graph export`/`salva run diff` | ✅ 完成 |
| C3 REST API 補完 | `GET /v1/runs/{run_id}`、`GET /v1/jobs/{job_id}`、`GET /v1/runs`、`GET /v1/jobs`、streaming events 全部實作 | ✅ 完成 |

---

## Phase 3 — Output Quality（差異化）

| 項目 | 描述 | 狀態 |
|---|---|---|
| B1 Research Report Schema | `salva_core/transforms.py` `build_research_report()` + `research_report` output profile：Executive Summary/Key Findings/Coverage Map/Coverage Gaps/Source Attribution；`MCP salva_research_report` 工具 | ✅ 完成 |
| D1 Project Isolation | `campaign_id` 字段已在 `ExecutionContext`；per-project SQLite 分離 DB 路徑待下一里程碑 | ⚠️ 部分(campaign_id done;DB 隔離 pending) |
| B2 Diff Output Mode | `salva run diff <run_id_a> <run_id_b>` CLI + `salva_run_diff` MCP 工具：added/removed/updated | ✅ 完成 |
| A4 BM25 Dedup 門檻 domain-aware | `processing/dedup.py` `BM25_DOMAIN_THRESHOLDS` + `MemoryDeduplicator(bm25_threshold=...)` + `service.py` 按 domain 注入(bd_leads/companies/taiwan_hardware=0.92, events=0.82) | ✅ 完成 |

---

## Phase 4 — 生產就緒

| 項目 | 描述 | 狀態 |
|---|---|---|
| D2 API Auth | `apps/api/auth.py` `require_auth` 已實作；`apps/api/main.py` main router 注入 `Depends(require_auth)`；MCP HTTP transport 驗 `SALVA_MCP_API_KEY` | ✅ 完成 |
| D3 Evidence 清洗 | `processing/scrubber.py` regex 過濾 API key/JWT/PEM/AWS key/hex secret；`extractor.py` snippet 落地前 `scrub_text()` | ✅ 完成 |
| E1 Graph Export CLI | `salva graph export --run-id <id> --format hif|dot` + `salva_graph_export` MCP 工具 | ✅ 完成 |
| E21 Live Benchmark | Real DDG + equal budget + pre-declared GT；驗 P≥0.60 R≥0.40 | ⏳ 腳本已就緒(`e21_live_benchmark.py`)，需 live 網絡執行 |
| E22 Memory Longitudinal | 同 domain 連跑 5 次量 recall curve；驗複利機制非假象 | ✅ PASS — seeds 0→62；nodes 16→78；recall 維持 0.60 |
| D1 Project Isolation DB | `project_id` 字段 + DB migration；`get_db_path_for_project()` per-file SQLite；`service.py` 路由到 project-specific DB；路徑遍歷防護；3 新測試 | ✅ 完成(含 per-file SQLite) |
| E17 Diff Longitudinal | `_compute_run_diff()` 驗：identical→empty；+1 entity→added；-1→removed；score delta→updated；4/4 PASS | ✅ PASS |
| E5b Entity Normalize | `normalize_alias()`+`resolve_entity_normalized()` in hold.py；NFKC+legal suffix strip(EN+CJK)；exact-first fallback；10/10 tests pass | ✅ 完成(embedding bridge deferred to omlx) |
