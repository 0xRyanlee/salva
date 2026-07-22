# Entity Resolution Integration Eval — Nomenklatura / Yente

Owner 拍板方向（`roadmap-20260721-build-vs-integrate.md`）：entity resolution 整合 FtM 生態而非手刻。本文件把方向坐實成可執行 spec。

## Nomenklatura 摘要

`pip install nomenklatura`（PyPI，最新 v4.12.0，2026-07-19；2005 commits，MIT）— **純 library，非常駐服務**。核心：
- `Resolver`：以 connected-components 演算法維護「這些 entity 是同一個」的判斷圖（judgements），可持久化到 SQLite/Postgres（`NOMENKLATURA_DB_URL`）。
- `Index`（blocking）+ `nomenklatura.matching`（評分算法，如 name-matching regression model）：候選配對產生 + 打分，比 Salva 現有的 regex legal-suffix 比對精緻。
- CLI：`nomenklatura xref`（產生候選）/ `dedupe`（互動確認）/ `apply`（把判斷寫回資料）。
- 操作對象是 **FtM `Entity`/`EntityProxy`**（`schema` + 型別化 `properties`），不是任意 dict。

無額外常駐依賴（Postgres/ES 都非必須，SQLite 夠用）——跟 Salva「自架、無 GUI、輕量」定位相容。

## Yente 摘要

`yente serve`（FastAPI async service）— **必須常駐服務**，且**強制依賴 Elasticsearch 或 OpenSearch**（indexing 核心，無法繞過），Jaeger tracing 為選配。最新 v5.5.0（2026-06-23），1978 commits，活躍。API 面向 bulk/watchlist matching（sanctions screening 用例：把候選名單灌進 ES index，批次比對）。

**對 Salva 是包袱不是加分**：Salva 目前零常駐 infra 依賴（SQLite-only），Yente 會強制引入一個 ES/OpenSearch cluster 只為了單次 discovery run 內的實體比對——用例不對稱（Yente 設計給「持久大型參考庫 + 高頻查詢」，Salva 是「per-run、stateless、caller 自己排程」）。

## Schema 對接成本

**關鍵發現：Salva 現有兩層常被混為一談，其實對應 Nomenklatura 的層次不同。**

1. `processing/dedup.py`（`MemoryDeduplicator`）操作對象是 `core/types.UnifiedResult`——**搜尋原始結果**（URL + title），在 entity 抽取**之前**，靠 URL normalize + BM25 title 相似度去重「同一篇文章被兩個搜尋引擎都回傳」。這層 **和 Nomenklatura 完全不重疊**——Nomenklatura 不處理原始文件去重，它處理已抽取的 entity 記錄之間「是否同一實體」。`processing/dedup.py` 應保持原樣，不在這次整合範圍內。
2. `salva_core/persistence/hold.py` 的 `normalize_alias`（regex 去法律尾綴）+ `resolve_entity_normalized`（exact → normalized-index → legacy 全表掃描 → GLEIF fallback 鏈）——**這才是真正的 entity resolution 層**，也是 Nomenklatura `Resolver`/`matching` 直接對應、可替換的部分。

  **意外發現**：`resolve_entity_normalized` / `resolve_canonical_id` 目前只在 `tests/test_hold_l1a_schema.py`、`test_e16_cjk_entity_resolution.py`、`test_e5b_entity_normalize.py` 被呼叫，`core/controller.py` 和 `apps/` 都沒有 wire 進 live pipeline（grep 全庫確認）。也就是說 Salva 現有的「entity resolution 層」是**已建但未接線的 scaffold**，不是正在跑的邏輯——這次整合的替換風險比想像低：沒有 live 呼叫路徑需要並行遷移。

3. `salva_core/schemas.py::CanonicalEntity` ↔ FtM `Entity`/`EntityProxy` 轉換點：
   - `entity_type`（Salva 扁平 7 值 Literal：lead/company/event/activity_signal/document/source/person）↔ FtM `schema`（Company/Person/LegalEntity 等百餘種階層 schemata）——需要一張映射表；`event`/`activity_signal`/`lead` 在 FtM 內建 schemata 沒有貼切對應，需透過 FtM 的 custom schema YAML 擴充機制（`FTM_MODEL_PATH`）自訂，否則會被迫塞進不精確的既有 schema。
   - `CanonicalEntity.attributes`（自由 dict）↔ FtM `properties`（每個 schema 型別化、非任意 key）——需要一層過濾/映射，非 schema-recognized 的 key 會被丟或需自訂 property 定義。
   - 其餘欄位（`title`→`caption`/`name` property、`source_urls`→`sourceUrl` property、`confidence`）大致可直接映射，成本低。

4. `salva_core/relation_ontology.py`（宣稱 FtM-aligned）：實測跟 FtM 只有**分類名稱**對齊（ownership/directorship/investment 等），語義上不同——`acting_in_concert` 是 Salva 自己在 `experiments/hg_penetration/`（`ftm_baseline.py`）已實證的差異化語義：FtM 的 Ownership 是 **reified 但本質二元**（owner/asset/percentage），一致行動人這種「群體層級」事實在二元分解下會丟失（該實驗顯示 FtM 二元對 75% concert bloc 控制結構誤判為「無控制股東」）。**relation_ontology.py 和 hold.py 的 hyperedge_incidences（n-ary）不在這次整合範圍內，保留**——Nomenklatura/FtM 管的是「entity resolution（哪些記錄是同一實體）」，不管「n-ary 關係表示」，兩者正交，整合 entity resolution 不影響 Salva 的超圖差異化主張。

## `dedup.py` 現況 vs 整合後保留/刪除

| 項目 | 現況 | 整合後 |
|---|---|---|
| `processing/dedup.py` 全檔（URL normalize + BM25 title 相似度 + `BM25_DOMAIN_THRESHOLDS`） | 原始搜尋結果去重，pre-entity | **保留不動** — 與 Nomenklatura 不同層，無重疊 |
| `hold.py::normalize_alias`（regex 去中英文法律尾綴） | entity resolution 的字串正規化 | **可刪除**，改用 Nomenklatura 的 name-matching（更精細、非硬編碼尾綴表） |
| `hold.py::resolve_entity_normalized` 的 exact/normalized-index/legacy 全表掃描鏈 | 手刻三段式比對 | **刪除**，替換為 `nomenklatura.Resolver` 的 connected-components 查詢 |
| `hold.py::resolve_canonical_id`（exact alias lookup） | 簡單 exact match | 可保留作為 Resolver 判斷前的 fast-path，或直接交給 Resolver 內部索引 |
| `hold.py` GLEIF fallback（`salva_core.resolvers.gleif`） | 外部法人登記庫查詢 | **保留** — 與 Nomenklatura 正交，且已是「整合外部源」而非手刻，符合方向 |
| `hold.py` hyperedge_incidences / canonical_entities upsert 骨架 | n-ary 儲存 + entity 註冊表 | **保留** — Nomenklatura 只提供「判斷」，寫入儲存仍是 Salva 的 Hold 負責，Hold 作為 source of truth 不變 |
| `relation_ontology.py` | FtM 分類名對齊、Salva 自有多方語義 | **保留** — 正交於 entity resolution，且是已驗證的差異化點 |

## 結論

**建議整合 Nomenklatura，不整合 Yente。**

- Nomenklatura：pip library、無常駐服務、SQLite 可用，跟 Salva「自架輕量、caller 觸發」定位完全相容；且要替換的 `hold.py` 目標函式目前是未接線 scaffold，遷移風險低、無需雙軌並行。
- Yente：強制 Elasticsearch/OpenSearch 常駐叢集，用例（bulk watchlist/sanctions screening 對大型持久參考庫）跟 Salva 的 per-run stateless discovery 不對稱，會違反「輕量自架」的既定定位。**不是不可行，是現階段不划算**——若未來 Salva 需要「against a large persistent reference corpus 的批次比對」（例如自建的跨 run 全域實體庫達到需要 ES 規模時）才重新評估 Yente，非現在。

## 下一步實作步驟（給後續實作卡當 spec）

1. 加 optional dependency group：`pyproject.toml` 新增 `resolution = ["nomenklatura>=4.12.0"]`（沿用現有 `[project.optional-dependencies]` 模式，不動 core `dependencies`）。
2. 新增 `salva_core/resolvers/ftm_adapter.py`：`canonical_entity_to_proxy(entity: CanonicalEntity) -> EntityProxy` 與反向函式；內含 `entity_type → FtM schema` 映射表（7 個值逐一決定：company/person 直接映射，event/activity_signal/lead/document/source 需自訂 schema 或選最接近的既有 schema 並記錄取捨）。
3. 找出目前 controller 多輪 merge 決策的實際呼叫點（`core/controller.py` 尚未定位到 entity-level merge 邏輯，需先 grep/trace 確認——本文件未涵蓋，是下一步的第一個發現任務），評估在該處或 `hold.py` 寫入路徑接入 `nomenklatura.Resolver`。
4. 用 `nomenklatura.Resolver` + `nomenklatura.matching` 替換 `hold.py::normalize_alias` 與 `resolve_entity_normalized` 的三段式鏈；`resolve_canonical_id` 可留作 fast-path 或整併進 Resolver 查詢介面。
5. GLEIF fallback、hyperedge_incidences、relation_ontology.py、processing/dedup.py 均不動。
6. 補 round-trip contract test：`CanonicalEntity → EntityProxy → CanonicalEntity` 在核心 7 欄位（entity_id/entity_type/title/source_urls/confidence/tags/attributes）無損；對 `attributes` 中非 FtM-schema-recognized 的 key，明確斷言其行為（丟棄或報警），不要讓它靜默消失。
7. 現有三份測試（`test_hold_l1a_schema.py` / `test_e16_cjk_entity_resolution.py` / `test_e5b_entity_normalize.py`）改寫為對 Nomenklatura-backed 實作跑同一組斷言（TSMC/Samsung/GIGABYTE 等既有 fixture 案例延用），確保行為不倒退。
8. 不做：Yente、Docker、Elasticsearch/OpenSearch 依賴。
