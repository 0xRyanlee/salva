# Salva Runtime 開發任務清單

> 完整的開發方向與設計原則請見 `CLAUDE.md`。
> 核心定位：Event-triggered, API-first, Agent-native Discovery Intelligence Runtime。
> 服務對象：任何方向的探索意圖，不假設特定行業或場景。

## 現況統計

- 完成：72
- 未完成：0
- 合計：72

## 建議執行順序

1. `L0` Probe-driven Topology Routing
2. `L1` Hold 超圖後端升級
3. `L2` Semantic Query Memory 品質升級
4. `L4` SaaS 與多租戶基礎

## 測試策略

- 一般開發先按 pipeline 跑最小回歸，不預設全量測試。
- 變更共享契約、路由、 persistence、API 形狀時，再升級到整合回歸。
- Release 前或大重構後，才跑全量 `pytest`。

---

## 文檔層

- [x] **建立 `docs/spec/` 作為 canonical contract layer**
- [x] **將大型總覽文件逐步降級成路線圖 / 歷史索引**
- [x] **讓 README / SKILL / quick reference 只保留入口與索引**
- [x] **建立 `docs/README.md` 作為文檔總入口**
- [x] **讓 README / SKILL 指向 canonical spec layer**

---

## 優先任務（阻塞型問題，先於其他開發）

### A：Query Intelligence 架構修正

> 目前 keyword_graph 與 query_strategy 的設計將服務的有效範圍限定在兩個硬編碼 domain，
> 任何不在其中的探索方向（公司調查、市場情報、合作信號、OSINT、學術研究…）都會退化
> 到無詞彙展開的裸跑狀態。這是影響通用性的根本問題，修復優先級最高。

---

#### A1：DomainVocab 改為可注入的 Registry 架構

**問題根源**（`core/keyword_graph.py:31`）

```python
_VOCAB: dict[str, dict] = {
    "events":   { ... },   # 硬編碼
    "bd_leads": { ... },   # 硬編碼
    # 其他任何 domain → 空 dict → 零展開
}
```

`query_strategy.source_hints_for_domain()` 同樣只有兩個 if 分支，任何新 domain 拿到的
是混合了活動站和 BD 站的無意義 fallback。

**修復方向**

- [x] **建立 `core/domain_vocab.py`，定義 `DomainVocab` dataclass**

  ```python
  @dataclass
  class DomainVocab:
      synonym_groups:  dict[str, list[str]]  # canonical → variants
      region_variants: dict[str, list[str]]  # region name → aliases
      signal_terms:    list[str]             # high-value trigger phrases
      source_hints:    list[str]             # site: 搜尋目標
      noise_terms:     list[str]             # 額外 negative 詞
  ```

- [x] **建立內建 domain 目錄**，現有兩個遷移過來作為參考實作：
  - `events` — 活動、論壇、展覽、講座
  - `bd_leads` — 通路、批發、分銷、B2B 夥伴
  - **新增** `companies` — 公司調查（公司名、資金、規模、產品、職缺信號）
  - **新增** `market_intel` — 市場情報（發布、公告、趨勢、競品動態）
  - **新增** `partnerships` — 合作信號（co-marketing、整合、joint venture、MOU）
  - **新增** `general` — 無 domain 時的通用 fallback（不繼承任何特定行業詞彙）

- [x] **`KeywordGraph.__init__` 接受可注入的 `vocab: DomainVocab | None`**
  - 有 vocab 參數 → 直接使用
  - 無 vocab → 從 registry 查 `domain` 名
  - registry miss → 使用 `general` fallback，不報錯

- [x] **`DiscoveryRequest.intent` 加入 `domain_hints` 可選欄位**

  呼叫端可在請求中直接注入領域知識，無需修改服務端代碼：
  ```json
  "intent": {
    "market": "US",
    "industry": "legal tech",
    "domain_hints": {
      "synonym_groups": { "contract": ["agreement", "NDA", "SLA", "MOU"] },
      "signal_terms":   ["compliance", "e-signature", "regulatory"],
      "source_hints":   ["law360.com", "legaltech.com", "g2.com"]
    }
  }
  ```

- [x] **`source_hints_for_domain()` 遷移到 `DomainVocab.source_hints`**
  - 刪除 `query_strategy.py` 中的 if/elif/else 分支
  - domain 的 source hints 由其 `DomainVocab` 持有

- [x] **`ScorerConfig` 對應整合**
  - `DomainVocab.noise_terms` 合併進 `ScorerConfig.negative_signals`
  - 讓 `QualificationScorer` 在無 explicit config 時從 `DomainVocab` 推導預設值

- [x] **補上 `DomainVocab` 的單元測試**
  - 測試 registry 查找邏輯
  - 測試 `domain_hints` 注入覆蓋 registry 預設值
  - 測試 `general` fallback 路徑

---

#### A2：修正 OBJECTIVE_TO_DOMAIN 映射

**問題根源**（`service.py:28`）

```python
OBJECTIVE_TO_DOMAIN = {
    "find_events":              "events",
    "find_exhibitors":          "events",
    "find_leads":               "bd_leads",
    "find_companies":           "bd_leads",    # ← 公司調查不應用 BD 詞彙
    "find_market_activity":     "bd_leads",    # ← 市場情報不應用 BD 詞彙
    "find_partnership_signals": "bd_leads",    # ← 合作信號不應用 BD 詞彙
}
```

- [x] **更新映射，對應 A1 新增的 domain**
  ```python
  OBJECTIVE_TO_DOMAIN = {
      "find_events":              "events",
      "find_exhibitors":          "events",
      "find_leads":               "bd_leads",
      "find_companies":           "companies",
      "find_market_activity":     "market_intel",
      "find_partnership_signals": "partnerships",
  }
  # 未匹配的 objective → "general"（不再默認 "bd_leads"）
  ```

- [x] **未知 objective 的 fallback 改為 `general`**
  - 目前 `dict.get(objective, "bd_leads")` → 改為 `dict.get(objective, "general")`
  - `general` domain 使用純 primary_terms 展開，不附加任何行業假設

- [x] **`objective` 欄位加入 schema 文件說明**（見 CLAUDE.md）
  - 明確列出內建 objective 清單及各自的 domain 映射
  - 說明呼叫端傳入未知 objective 的行為（退化到 general，不報錯）

- [x] **補上映射變更的回歸測試**（在 tests/test_domain_vocab.py）
  - 確認 `find_companies` 不再繼承 `bd_leads` 的 signal_terms
  - 確認 `find_market_activity` 使用 `market_intel` 詞彙
  - 確認未知 objective 用 `general` 而非 `bd_leads`

---

#### A3：語義記憶 Bootstrap 接線

**問題根源**

`query_family_memory` 表存在、`/v1/semantic/query-families` API 存在，但
**新 run 開始時沒有任何代碼讀取過去成功的 query family 來 prime 初始 graph 節點**。
系統在單次 run 內的輪間學習（intra-run telemetry feedback）正常工作，但跨 run 的
跨會話學習完全沒有接線，語義記憶形同廢置。

- [x] **在 `KeywordGraph` 加入 `seed_from_memory()` 方法**

  ```python
  def seed_from_memory(
      self,
      memory_reader: Callable[[str, int], list[dict]],
      top_k: int = 5,
      seed_weight: float = 0.5,
  ) -> int:
      """
      讀取過去成功 query family，將高分節點注入初始 graph。
      在 _bootstrap() 之後、第一輪搜尋之前呼叫。
      返回實際注入的節點數。
      """
  ```

  - `memory_reader` 是可注入的 callable，避免 KeywordGraph 直接依賴 persistence 層
  - 從記憶中取 top_k 個 query family（按 success_score 排序）
  - 將其 `source_nodes` 中不重複的節點注入，初始 weight = seed_weight（低於 primary 的 1.0）
  - 注入節點標記為 `node_type="memory"`，便於 telemetry 追蹤

- [x] **在 `service.py:execute_discovery()` 中呼叫 `seed_from_memory()`**
  - 在 `SalvaController` 初始化後、`controller.run()` 前
  - `memory_reader` 從 `salva_core.persistence` 取成功 query family 的函式
  - 加入 `meta` 中：`"memory_seeds_used": n`（供 audit 追蹤）

- [x] **`memory_reader` 介面定義在 `salva_core/schemas.py`**（callable 協議，測試可 mock）
  - 讓 memory seeding 可在測試中被 mock 替換

- [x] **補上 `seed_from_memory()` 的單元測試**
  - 測試有記憶時正確注入節點
  - 測試無記憶時靜默不報錯
  - 測試 `node_type="memory"` 節點不被 `prune()` 在首輪前清除

---

### B：Probe-driven Topology Routing

> 用戶通常知道目標，不知道檢索形狀。系統需要先 probe，判斷這題更像 vertical / broad / concentrated / distributed / structured / mixed，
> 再決定 route、source pack、fanout、merge policy 與錯誤表面。

#### B1：Topology probe schema

- [x] **建立 `docs/spec/topology-probe.md`**
  - 定義 `Probe -> Topology -> Route Plan -> Execute -> Re-plan` 的決策鏈
  - 列出 topology taxonomy：`vertical`, `broad`, `concentrated`, `distributed`, `semantic_union`, `structured`, `unstructured`, `mixed`
  - 明確要求錯誤 surface 帶上 `stage / code / route / provider / topology / query / message / actionable_hint`

- [x] **把 topology probe spec 接到索引文件**
  - `docs/spec/README.md`
  - `docs/README.md`
  - `docs/README.zh.md`
  - `docs/spec/error-contract.md`、`docs/spec/retrieval-contract.md`、`docs/spec/route-catalog.md`、`docs/spec/debug-playbook.md` 都要引用它

- [x] **新增 probe output schema**
  - 新增 `TopologyProbe` / `RoutePlan` 類型
  - 輸出至少包含 `topology`, `confidence`, `recommended_route`, `source_pack`, `strategy_bias`, `fanout_policy`, `merge_policy`
  - 讓 caller 能先看懂「系統認為這題是什麼形狀」

- [x] **新增 probe-aware planner**
  - 先 probe，再決定 route catalog entry
  - 讓 `objective -> route` 變成 `objective -> probe -> topology -> route`
  - 支援重新規劃，而不是一輪定死

- [x] **擴充 error envelope**
  - 統一輸出 `stage / code / route / provider / topology / query / actionable_hint`
  - 把 `500 Internal Server Error` 拆成可追溯的類型
  - 讓 agent / CLI / API 都能直接定位根因

- [x] **補 probe / route 的回歸測試**
  - 測試 topology classification 的穩定性
  - 測試 probe 失敗時的 fallback 表現
  - 測試錯誤 envelope 是否帶齊 stage 與 topology

#### B2：Planner / preprompt policy

- [x] **建立 planner / preprompt spec**
  - 定義 `planner.md`：輪次規劃、完整度門檻、replan 條件
  - 定義 `preprompt.md`：歧義評分、澄清問題、正規化目標

- [x] **新增 planner API**
  - 建立 `POST /v1/planner`
  - 輸出 `probe / route_plan / preprompt / plan / experience_plan`

- [x] **讓 planner 產生 round budget 與 stop conditions**
  - `structured / vertical` 偏低輪次與高精度
  - `broad / distributed / mixed` 偏高輪次與廣覆蓋

- [x] **加入必要時的 LLM preprompt**
  - 當歧義高時，以 OMLX 生成 1-3 個澄清問題
  - 不可用時回落到規則版 preprompt

- [x] **補 planner / preprompt 回歸測試**
  - 測試歧義高時會詢問
  - 測試歧義低時直接進入 plan
  - 測試 LLM preprompt fallback 行為

---

## 代碼品質重構

### R1：核心模組瘦身

- [x] **拆分 `salva_core/persistence.py`（1908 行）→ 6 子模組**
  - `persistence/db.py`（427 行）— schema、連線、migration
  - `persistence/runs.py`（652 行）— run 寫入（含 evidence/relations/hyperedges 等原子事務）+ 讀取
  - `persistence/jobs.py`（262 行）— job queue + stream events
  - `persistence/telemetry.py`（155 行）— telemetry / source_attempts / plugin_reports 讀取
  - `persistence/evidence.py`（277 行）— evidence chains / relations / hyperedges 讀取
  - `persistence/memory.py`（192 行）— query family memory / semantic search / seeding
  - `persistence/__init__.py`（81 行）— 統一對外 API，對外介面不變
  - ⚠️ `runs.py` 超過 350 行：`persist_discovery_run` 是不可拆分的原子事務，這是正確的設計取捨

- [x] **收斂 `schema/` legacy bridge**
  - 類型定義移至 `core/types.py`（Intent, KeywordNode, KeywordEdge, QueryFamily, SearchTelemetry, UnifiedResult）
  - 所有 10 個生產代碼 imports 已改為 `from core.types import ...`
  - `schema/` 兼容層已刪除，測試與打包入口已改為直接使用 `core.types`

- [x] **mypy strict 逐步全覆蓋**
  - 已覆蓋 `salva_core/`、`salva_sdk/`、`retrieval/`、`processing/`、`enrichment/`
  - 每個模組 strict 通過後已在 `pyproject.toml` 加入對應 package

- [x] **測試覆蓋率稽核**
  - 已執行 `pytest --cov --cov-report=term-missing`
  - 目前整體覆蓋率約 85%
  - 低覆蓋模組已開始逐步補測試，維持原子化收斂

---

## 整合層

### R2：MCP Server（核心整合面，優先）

- [x] **建立 `apps/mcp/` 目錄與 MCP server 入口**
  - `apps/mcp/server.py`（FastMCP，6 個工具）
  - `apps/mcp/__main__.py`（stdio / HTTP 雙模式，`python3 -m apps.mcp`）
  - 使用 `mcp` Python SDK（`pip install 'salva-runtime[mcp]'`）

- [x] **實作核心 MCP tools**

  | Tool | 功能 | 說明 |
  |------|------|------|
  | `salva_discover` | 同步探索 | max_results ≤ 20，直接返回 entities |
  | `salva_job_create` | 非同步 job | 大規模，返回 job_id |
  | `salva_job_status` | 查詢 job 進度 | 輪詢，返回 status + run_id |
  | `salva_run_result` | 取完整結果 | entities + evidence + meta |
  | `salva_audit` | 稽核報告 | 品質分析 |
  | `salva_pilot` | 下一步建議 | 搜尋策略建議 |

- [x] **建立 route index**（`/v1/routes`、`/v1/routes/{route_name}`）

- [x] **domain_hints 注入支援**（`domain_hints_json` 參數）
- [x] **stdio + HTTP 雙模式**（`--transport stdio/http`）
- [x] **直接 import salva_core，不需要 FastAPI 服務運行**
- [x] **MCP 整合測試**（Tool schema 合規驗證）

### R3：CLI Skill Wrapper

- [x] **建立 `apps/cli/` 目錄**，入口 `apps/cli/main.py`，使用 `typer`

- [x] **核心命令**（`pip install 'salva-runtime[cli]'`）
  ```bash
  salva find   --market <market> --industry <industry>
  salva job    status <job_id>
  salva job    list
  salva run    show <run_id>
  salva audit  <run_id>
  salva pilot  <run_id>
  salva vocab  list
  salva vocab  show <domain>
  ```

- [x] **`--json` flag** — 純 JSON stdout，供 agent pipeline 消費
- [x] **`--domain-hints` JSON 注入支援**
- [x] **`pyproject.toml` 加入 CLI entry point** (`salva = "apps.cli.main:main"`)

### R4：Python SDK

- [x] **建立 `salva_sdk/` package**
- [x] **同步 + 非同步 client**，介面只依賴 REST API
  ```python
  from salva_sdk import SalvaClient
  client = SalvaClient(base_url="http://localhost:8000")
  # domain_hints 直接透傳到 API
  result = client.discover(
      market="Germany", industry="legal tech",
      domain_hints={"signal_terms": ["compliance", "e-signature"]}
  )
  ```
- [x] **SDK 文件**（`docs/sdk.md`）

### R5：整合設計文件

- [x] 核心原則記錄於 `CLAUDE.md`
- [x] **`docs/event-driven-integration.md`**（MCP / CLI / REST / SSE 整合模式）
- [x] **`docs/domain-vocab-guide.md`**（built-in domains / domain_hints / register_domain）

---

## 安全與部署

### R6：Auth 邊界（發布前必要）

- [x] **設計 auth 邊界**：Static API key（`X-Salva-Key`）
- [x] **`apps/api/auth.py`**，FastAPI `dependencies=[Depends(require_auth)]` 全局注入
  - `SALVA_API_KEY` 空值 = 開發免認證模式；非空 = 強制驗證
- [x] **MCP server auth**（MCP transport 層無標準 auth；env-based key check）

### R7：Docker 與部署

- [x] **`.env.example`** — 所有環境變數模板，無真實值
- [x] **`docker-compose.yml` 加入 MCP service**（salva-api / salva-mcp / salva-worker）
- [x] **Health check 與 graceful shutdown**

---

## 未完成的功能任務

### F1：OSINT Plugin 完整整合

- [x] **theHarvester 整合**（條件安裝）
  - 確認執行路徑，補上錯誤處理
  - 補上整合測試
- [x] **Amass 整合**（條件安裝）
  - 同上
- [x] **SpiderFoot adapter 驗證**（已有 stub，需實際測試）

---

## 長期方向

### L1：Hold 超圖後端升級

- [x] 評估 DuckDB + graph extension / neo4j / kuzu
  - 已新增 `/v1/hold/backends`，把 SQLite / DuckDB / Neo4j / Kuzu 的評估面暴露成 read model
- [x] 設計 relation-aware retrieval API（圖遍歷查詢）
  - 已落地 `/v1/hold/walk`
- [x] `entity → evidence → source → related_entity` graph walk 能力
  - 已落地 Hold snapshot graph walk read model

### L2：Semantic Query Memory 品質升級

- [x] **建立 semantic index catalog / 觀測入口**
  - 已公開 `/v1/semantic/indexes` 與 `docs/spec/semantic-memory.md`
- [x] 目前 `query_family_memory.vector` 已升級為 deterministic hybrid backend
- [x] 評估 sqlite-vec / hnswlib / faiss 作為本地向量索引（A3 完成後展開）
  - **結論**: 首選 sqlite-vec（與 SQLite 原生整合，基於 Faiss）
  - 備選 hnswlib（高效能獨立庫）
  - 實施优先级：中（需先完成 schema 設計）

- [x] `seed_from_memory()` 的召回品質依賴向量精度，L2 是 A3 的長期升級
  - **現況**: semantic_vectors 表僅存 JSON，無 ANN 索引
  - **長期方向**: 遷移到 sqlite-vec + HNSW 索引
  - **短期優化**: 可先增加 top_k 數量compensate 精度不足

### L3：GUI Fork（獨立倉庫）

> 不在此倉庫開發。基於 REST API + MCP contracts，獨立 GitHub repo 發布。

### L4：SaaS 與多租戶（遠期，依賴 R6）

- [x] Tenant-aware job + storage model
  - `jobs.tenant_id` 已落地，`JobRecord` 也直接暴露 tenant；後續再做 DB schema 級多租戶隔離
- [x] Quota + rate-limit 模型
  - 已新增 `/v1/quota` 與 tenant-aware 封鎖，限制為 env-driven 的讀模型
- [x] Billing-friendly usage telemetry
  - 已新增 `/v1/usage`，並以 tenant-aware 聚合 runs / jobs / telemetry / source attempts

---

## 稽核驗證清單

> 定期對照代碼，確認問題是否已修復。

| 問題 | 位置 | 狀態 | 修復任務 |
|------|------|------|----------|
| `_VOCAB` 硬編碼 domain 詞彙 | `core/keyword_graph.py:31` | ✅ 已修 | A1 |
| `source_hints_for_domain()` 硬編碼 | `core/query_strategy.py:209` | ✅ 已修 | A1 |
| `find_companies` 等 objective 錯誤歸到 `bd_leads` | `service.py:28` | ✅ 已修 | A2 |
| 語義記憶未接線到 bootstrap | `core/keyword_graph.py` | ✅ 已修 | A3 |
| `persistence.py` 單檔 1908 行 | `salva_core/persistence.py` | ✅ 已修 | R1 |
| `schema/` legacy bridge 未收斂 | `schema/intent.py` | ✅ 已修 | R1 |
| OSINT plugins 執行路徑未驗證 | `enrichment/` | ✅ 已修 | F1 |
| Vector memory 是標量嵌入 | `persistence.query_family_memory` | ⚠️ 已知限制 | L2 |
| API 無認證層 | `apps/api/` | ✅ 已修 | R6 |
