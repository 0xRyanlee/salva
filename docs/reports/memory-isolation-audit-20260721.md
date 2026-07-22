# Memory / Quarantine / Promotion 隔離審計（2026-07-21，唯讀）

範圍：`salva_core/persistence/memory.py`、`db.py`、`runs.py`，及 `query_family_memory`/`seed_from_memory`/`search_query_family_memory`/promotion 全部呼叫點（`core/`、`apps/`、`salva_core/`）。不改任何檢索邏輯。

## 隔離契約現況盤點

**分層機制**：`ExecutionContext.memory: MemoryPolicy`（`salva_core/schemas.py:266-345`）——`read_scope`（`none`預設 / `campaign_promoted` / `campaign_all` / `global_legacy`）+ `write_mode`（`none` / `quarantine`預設 / `promote`）。`campaign_promoted`/`campaign_all`/`write_mode=promote` 都在 `_validate_memory_scope` 強制要求 `campaign_id` 存在，`persistence=none` 會強制 `write_mode=none`（schemas.py:338-346）。

**寫入路徑**：`salva_core/persistence/runs.py:278-374`，`memory_status = "promoted" if write_mode=="promote" else "quarantine"` ——**promotion 完全由呼叫端當次宣告的 policy 決定，不是任何品質量測的結果**。寫入當下不檢查 `success_score`。這與 `docs/reports/execution-isolation-update-2026-06-08.md` 描述一致（quarantine 為預設，promote 需顯式聲明）。

**讀取路徑的品質閘**：真正的品質過濾在讀取端——`read_top_query_families_for_seeding`（memory.py:200-248）不論 `read_scope` 為何，一律套 `WHERE success_score >= min_success_score`（預設 0.3，`MemoryPolicy.min_success_score`）。`campaign_all` 會讀 quarantine + promoted（不過濾 `memory_status`），但仍受 `success_score` 門檻擋住。`campaign_promoted` 額外加 `memory_status='promoted'`。所以「低品質結果被 promote」本身不是威脅——威脅點若存在，是在讀取端漏掉 `success_score` 或 `campaign_id` 過濾。

**資料庫層 scope 欄位**：`query_family_memory` 表有 `run_id`、`campaign_id`、`continuation_id`、`memory_status` 四個 scope 欄位，`db.py:322-325` + `:551-558` 有對應索引（`run_id`/`objective`/`strategy`/`signature`/`domain`/`campaign_id`/`memory_status`）。專案（project_id）層級是**物理隔離**——`get_db_path_for_project()`（db.py:35-43）把每個 project 導向不同 SQLite 檔案，campaign/status 才是同檔案內的邏輯過濾。

**呼叫點盤點**（8 處）：`service.py:_seed_graph_from_memory`（discover 主流程種子注入，正確依 `read_scope` 決定 `campaign_id`/`memory_status`）、`api/main.py` 的 `/v1/query-families`、`/v1/semantic/query-families`、`/promote`（瀏覽/手動促升端點，`campaign_id` 選填）、`navigation.py:_build_semantic_matches`（pilot 建議用，只傳 `objective`，未傳 `campaign_id`）、`exporting.py`（依 `run_id` 精確匯出，安全）、`semantic.py:build_semantic_backend_benchmark`（benchmark 專用，讀樣本不分 campaign）、`stability.py:compute_stability_signals`（見下方缺口）。

## 發現的具體缺口

**缺口 1（真實且目前可觸發，判定：live，非 dormant——主線複核修正）**：`salva_core/stability.py:42-44` 呼叫 `list_query_family_memory(limit=fetch_limit, path=path)` **完全沒有帶 `campaign_id` 也沒有帶 `memory_status`**，把同一 domain 底下所有 campaign、含 quarantine（未驗證/失敗）記錄一起撈回來算 drift/volatility，結果經 `w_stability` 灌回 `processing/scorer.py:276-279` 的 composite score（`salva_core/service.py:252-283` 的 `_build_stability_scoring_context`）。

原稿判定「`DiscoveryRequest` 沒有 `stability` 欄位、不可達」**經複核為誤判**：`salva_core/schemas.py:534` 上 `DiscoveryRequest.stability: StabilityPolicy | None` 是已存在的真實欄位（`StabilityPolicy.enabled` 預設 `False`，僅此而已）。且**兩個對外介面都已直接暴露這個開關**：
- MCP：`apps/mcp/server.py:96` `salva_discover(..., enable_stability_gating: bool = False)` 直接構造 `StabilityPolicy(enabled=enable_stability_gating)`（server.py:133）。
- REST：`/v1/discover` 直接吃 payload 裡的 `stability: {"enabled": true, ...}` 欄位（`tests/integration/test_discover_endpoint.py:64-90` 證實 zero extra route code，Pydantic 欄位自動生效）。

也就是說，**任何呼叫方今天就能透過 MCP 傳 `enable_stability_gating=True` 或 REST 傳 `stability.enabled=true` 立即觸發跨 campaign、跨 quarantine/promoted 的分數污染**，不需要等誰去改 schema——這不是「已寫好但未接線的地雷」，是「已接線、預設關閉、呼叫方一個布林值就能引爆」的現貨缺口。嚴重性上修為**高**：兩個公開介面（MCP + REST）都是攻擊面，且無需特殊權限。

建議修復方向：`compute_stability_signals`/`list_query_family_memory` 呼叫鏈應接受 `campaign_id`（可選，行為對齊 `read_scope`）並預設只吃 `memory_status='promoted'`，在 `enable_stability_gating`/`stability.enabled` 開放給呼叫方之前必須先補上這層過濾——這應該是一張獨立的高優先修復卡，不只是文件建議。

**缺口 2（功能性，非洩漏）**：`apps/api/main.py` 的 `/v1/query-families`、`/v1/semantic/query-families`、`/v1/query-families/{id}/promote` 三個端點都沒有 `project_id` 參數，一律打 `DEFAULT_DB_PATH`；但 `/v1/discover` 寫入走 `get_db_path_for_project(execution.project_id)`，非預設 project 的記錄會落在 `data/projects/<id>/salva.db`。結果是這三個端點對有 `project_id` 的 campaign 完全「看不見」（無法瀏覽、無法手動 promote），不是跨租戶外洩，是可用性缺口。

**未發現的缺口**：`campaign_promoted`/`campaign_all`/`write_mode=promote` 的 schema 層強制 `campaign_id`；手動 `/promote` 端點的 SQL `WHERE memory_id=? AND campaign_id=?` 同時比對兩者，不能只憑 `memory_id` 跨 campaign 促升；`source_hints` 只餵給 query 建構（`core/query_strategy.py`），從未進入 `processing/scorer.py` 的 `TRUSTED_SOURCES`，`source_hints` 自我宣告信任的攻擊面確實被擋住，與六週前文件的宣稱一致。

## 對 execution-isolation-update-2026-06-08.md 的現況校驗

**仍準確**：read/write 預設值、`campaign_promoted`/`campaign_all`/`persistence=none` 語意、`source_hints` 不進信任清單、四張表核心欄位、`isolation-report.json` 六項對抗測試檔案仍在（`experiments/agent_vs_salva/isolation-report.json`，6/14 更新）。**仍是開放項、未過時只是未做**：文件自己列的「Remaining Work」（reviewer identity、promotion reason、provenance hash、rejection state、promotion audit log）六週後仍未實作——`promote_query_family_memory`（memory.py:251-283）只有 `memory_id`+`campaign_id`，沒有審核者/理由/來源雜湊欄位，這不是文件過時，是文件準確描述了尚待做的事。文件沒提到的是 `stability.py` 這條新通道（可能是文件當時 `StabilityPolicy` 還沒寫），屬於文件範圍外的新增風險面，建議下次更新此文件時補上。

## 建議

1. 修 `stability.py` 的 campaign/status 過濾，在 `DiscoveryRequest` 真的接上 `stability` 欄位之前處理掉，不要等它變成活路徑才修。
2. 若要讓 `/v1/query-families` 系列端點對 project-scoped campaign 可用，補 `project_id` query 參數並轉呼 `get_db_path_for_project`。
3. 其餘沿用文件既有的 Remaining Work 清單（review workflow / artifact isolation）即可，不需新增。

## 結論摘要

盤點後找到一個真實且**目前可觸發**的高嚴重性缺口（主線複核修正了子agent原稿的「不可達」誤判）：`salva_core/stability.py:42-44` 讀 query family memory 時沒有 `campaign_id`/`memory_status` 過濾，MCP 的 `enable_stability_gating=True` 或 REST 的 `stability.enabled=true` 兩個現有公開參數都能直接觸發，造成跨 campaign、跨 quarantine 污染評分——預設關閉但呼叫方隨時可開。另有一個非洩漏的功能缺口（REST 瀏覽端點不吃 `project_id`）。核心 discover 種子注入路徑（`service.py:_seed_graph_from_memory`）、promotion 寫入/讀取的品質閘、campaign 強制校驗都正確。六週前的隔離文件現況仍準確。
