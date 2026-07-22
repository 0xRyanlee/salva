# 運維穩定性審計 — provider fallback / quota / telemetry / job lifecycle

**日期**：2026-07-21
**性質**：唯讀審計，不含代碼修改
**背景**：`experiments/salva_v2/PROVIDER_ISOLATION_FINDINGS.md` 涵蓋檢索品質面（ddgs/ddg_html/searxng 各自準確度），本審計只涉及運維穩定性面（降級路徑、計量正確性、可觀測性、job 狀態機），兩者不重疊。

## 1. Provider fallback 與健康狀態

現況：`retrieval/health.py` 的 `ProviderHealth` 是每 provider 的 circuit breaker（連續失敗 3 次觸發 cooldown，依錯誤類型 1 分鐘到 24 小時不等），`retrieval/router.py` 的 `RoutedRetriever._search_sequential/_search_parallel/_search_adaptive` 依健康狀態跳過 cooldown 中的 provider，逐一 fallback。

風險點：
- **健康狀態鍵值過粗**：`router.py:182-184` 的 `_provider_id()` 只用 `type(provider).__name__` 當 key，不含 base_url/instance。若 caller 透過 `policy.providers` 配置同一 kind 的多個不同端點（如兩個不同 `searxng` base_url），其中一個失敗會拖累健康記錄，另一個健康正常的實例也被誤判 cooldown。理論風險，預設 chain（`registry.py:_build_default_chain`）每種 kind 只建一個實例，不觸發。
- **process-global 無鎖共享狀態**：`retrieval/health.py:114` 的 `_DEFAULT_REGISTRY` 是進程級單例，被所有並發 run/tenant/campaign 共用，且 dict 讀寫無鎖。多產品併發下，某一 campaign 的爆量查詢把某 provider 打進 RATE_LIMIT/BLOCKED（4 小時 cooldown，`health.py:27-34`），會讓同進程內所有其他不相關 campaign 在這 4 小時內也失去該 provider —— 這是設計選擇（上游限流本來就是共享的），但值得標記為「無租戶隔離」的已知行為。
- **靜默降級，無訊號**：`router.py:_search_sequential`（67-100 行）在所有 provider 失敗或無內容時只回傳空/best-effort 結果，`salva_core/service.py` 的 `_collect_source_attempts`/`_collect_telemetry` 雖記錄了逐一 attempt，但這些記錄只在 `request.execution.persistence == "audit"` 時才落庫（`salva_core/worker.py:51`）。`DiscoveryResponse.meta` 沒有任何 `degraded`/`providers_exhausted` 欄位（全庫搜尋確認無此語意）。若 caller 用 `persistence="none"`，provider 全滅與「主題本來就沒結果」在回應層完全無法區分。**嚴重性：中高，是任務點名的 silent failure 情境。**

## 2. Quota / usage 計量

現況：quota 執行邏輯在 `salva_core/quotas.py`，`salva_core/persistence/usage.py` 只是唯讀聚合報表，本身不做計量或扣減。

風險點：
- **分頁截斷導致系統性低估用量（嚴重）**：`quotas.py:53-54` 呼叫 `list_runs(path=path)` 與 `list_jobs(path=path)`，兩者未傳 `limit`，各自預設 `limit=20`（`runs.py:390`、`jobs.py:122`），且是全域 `ORDER BY created_at DESC`（非按 tenant 過濾後再排序）。只要系統累計超過 20 筆 run/job（多產品環境下極容易），`_build_window`（`quotas.py:84-118`）拿到的只是全域最新 20 筆的子集，某租戶在窗口內的較舊記錄會被其他租戶的新記錄擠出分頁，quota 用量被低估 —— 租戶可能已遠超 hourly/daily 上限但檢查仍顯示 `allowed=True`。這是四項風險中最直接會在多產品/多 campaign 場景爆掉的一個。
- **check-then-act 競態**：`apps/api/main.py:249-250`（discover）與 `:299-300`（job create）都是「先 `evaluate_tenant_quota` 讀取狀態，再放行」，中間無原子扣減或鎖。兩個並發請求同時逼近上限時會同時通過檢查，quota 只是 soft check，非硬性 cap。**嚴重性：中，需要邊界附近的並發觸發，但自動化多 campaign 呼叫方正好容易產生這種爆量。**
- Quota 預設關閉（`quotas.py:25-33`，需設 `SALVA_TENANT_*_LIMIT` 環境變數才啟用）——這是合理預設，但代表沒有設定就完全沒有用量護欄，純粹依賴 owner 主動開啟。
- `usage.py` 純聚合、無計量職責，盤點後**未發現**它自身有 race condition 風險。

## 3. Telemetry 可觀測性

- Job 層級失敗完整記錄：`salva_core/worker.py:112-126` 的 `except Exception` 會呼叫 `update_job_status(..., "failed", error=str(exc))` 並 `append_stream_event(..., "job_failed", ..., {"error": str(exc)})`，透過 `/v1/jobs/{job_id}` 或 `/v1/jobs/{job_id}/events` 可查得失敗原因。**此路徑無問題。**
- 逐一 provider/source attempt 失敗記錄豐富（`source_attempts` 表含 base_url/succeeded/error/format_used），但同樣受限於 `persistence == "audit"` 才落庫，非預設以外的模式下無跡可尋（同第 1 項）。
- **LLM enrichment 失敗只寫 Python logging，不進任何 telemetry 表**：`enrichment/omlx.py:81-90` 的重試失敗只 `logger.warning(...)`，沒有寫入 `telemetry_records`/`source_attempts`/`plugin_reports` 任何一張表。這代表 OMLX/enrichment 整層掛掉時，`/v1/audits` 或 `salva_audit` 完全看不出來，只能翻進程的 stdout/stderr（若部署方沒外接日誌收集，重啟即遺失）。**嚴重性：中高 —— 這正是任務點名要查的 enrichment 失敗路徑，目前是真的會吞掉訊號。**
- DB 寫入失敗：`worker.py` 內的 `try` 區塊涵蓋 `persist_discovery_run` 等呼叫，失敗會被捕捉並記為 job "failed"。但 `update_job_status` 本身的呼叫（包含 except handler 內用來記錄失敗狀態的那次呼叫）不在任何保護傘內——若這次寫入自己因鎖等待逾時失敗（見第 4 項的 SQLite 鎖分析），例外會直接往上拋，且不會有任何 stream_event 記錄這次失敗，job 狀態卡在寫入失敗前的狀態。

## 4. Job 生命週期一致性

狀態機（文字版）：
```
queued --[create_job]
queued --claim_next_job / inline run_job--> running
running --成功--> completed
running --例外--> failed
{queued, failed(force), running(force)} --MCP salva_job_cancel--> cancelled
```

風險點：
- **Cancel 無 REST 對應端點**：`apps/api/main.py` 沒有任何 `/v1/jobs/{job_id}` 的 DELETE/POST-cancel 路由，cancel 只存在於 MCP（`apps/mcp/server.py:313-338`）。CLAUDE.md 的目標架構列了 `salva_job_cancel` 為 MCP 工具，但 REST 面完全空缺，屬完整性缺口。
- **Cancel 不是真中斷，且會被完成回寫覆蓋（高風險）**：`salva_job_cancel`（`apps/mcp/server.py:335-336`）只做 `update_job_status(job_id, "cancelled", ...)`，是純 DB flag flip。`run_job`（`worker.py:26-127`）內沒有任何 cancellation token 或 checkpoint 供執行中的 `service.execute_discovery` 查詢。若 job 正在跑（同步 inline 或獨立 worker 進程），force cancel 後底層執行仍跑到完成，隨後 `worker.py:77-83`（成功）或 `:113-119`（失敗）的 `update_job_status` 會把狀態**覆寫回 completed/failed**，"cancelled" 狀態悄悄消失。對預期 cancel 能真正停止工作的多 campaign 編排方，這是實質性的行為落差。
- **孤兒 running 態、無 heartbeat/timeout 回收機制（高風險）**：`claim_next_job`（`jobs.py:219-249`）只挑 `status='queued'` 的 row；job 轉成 running 後，`worker_id` 只在 claim 當下寫入一次，之後不再更新，全庫搜尋 heartbeat/timeout/reaper/stale 均無結果。worker 進程若崩潰（OOM/SIGKILL），該 job 永久卡在 "running"，沒有任何機制把它收回 queued 或標記 failed，輪詢 `/v1/jobs/{job_id}` 的呼叫方會無限等待。這是任務點名的孤兒中間態情境，且**目前完全沒有恢復路徑**。
- **併發寫入的鎖爭用**：`claim_next_job` 本身的原子 `UPDATE ... WHERE status='queued'`（`jobs.py:236-244`）設計正確，不會有雙 worker 搶到同一 job 的問題。但 `salva_core/persistence/db.py:374` 的 `sqlite3.connect(resolved_path)` 未設定 `timeout=`、未開 WAL 模式，多產品併發寫入（多個 job 的 `update_job_status`/`append_stream_event`/`persist_discovery_run` 同時打同一 db 檔）在超過預設 5 秒鎖等待後會拋 `database is locked`，此例外未在 jobs/runs 持久層做特別包裝，容易在高併發下轉為未預期的 500 或如第 3 項所述的狀態寫入半失敗。

## 結論摘要

四個範圍都有實際發現，非全部理論風險。最嚴重兩點：(1) `salva_core/quotas.py:53-54` 因未傳 `limit` 而預設只掃最新 20 筆 run/job，多產品環境下 quota 用量會被系統性低估，形同虛設；(2) job cancel（`apps/mcp/server.py:335-336`）只是 DB flag flip，無真中斷能力，且會被執行完成的回寫覆蓋，加上 "running" 態無 heartbeat/timeout 回收（`jobs.py` 全檔案），worker 崩潰會留下永久孤兒 job。次要但仍值得排入待辦：LLM enrichment 失敗只進 process log 不進 telemetry 表（`enrichment/omlx.py:81-90`），以及 provider 全滅時無 degraded 訊號回應給呼叫方。
