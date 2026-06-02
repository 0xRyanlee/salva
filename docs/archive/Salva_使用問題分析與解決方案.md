# Salva Runtime 使用問題分析與解決方案

**來源**：對話日誌 (`對話log.md`)  
**分析日期**：2026年5月  
**目標**：記錄使用 Salva Runtime 過程中遇到的問題，並提出解決方案

---

## 一、概述

本次對話記錄了使用 Salva Runtime 進行以下任務的過程：
1. 台灣 AI/科技職缺調研
2. 嘗試啟動 Salva Runtime 服務
3. 進行 Salva skill 代码审计
4. 横向对比 Salva 搜索效果
5. 多维度检索能力评估
6. 全局代码审计
7. 整合开发任务计划与执行

---

## 二、發現的問題清單（已更新解決狀態）

### 2.1 環境配置問題

| 問題 | 嚴重程度 | 狀態 | 解決方案 |
|------|---------|------|---------|
| 系統 Python 版本過舊 (3.9.6) | **P0** | ✅ 已解決 | pyproject.toml 明確 `requires-python = ">=3.11"` |
| 多個 venv 路徑混用 | **P1** | ✅ 已解決 | 統一使用 `~/.venvs/salva-runtime` |
| 依賴未聲明 (無 requirements.txt) | **P1** | ✅ 已解決 | 添加 `requirements.txt` |

**解決時間**：2026年5月

---

### 2.2 Salva-search Skill 問題

| 問題 | 嚴重程度 | 狀態 | 解決方案 |
|------|---------|------|---------|
| run_search.sh 硬編碼 openclaw 路徑 | **P1** | ✅ 已解決 | 改為靈活路徑檢測 (`VIRTUAL_ENV`) |
| max_provider_attempts=2 導致 ddgs 永不執行 | **P0** | ✅ 已解決 | 改為 `max_provider_attempts: 3` |
| ddgs 對中文查詢嚴重偏置 | **P2** | ✅ 已解決 | 添加 `--language` 參數支持 |
| 查詢語言/地區控制缺失 | **P1** | ✅ 已解決 | `provider_router.py` 新增 language 參數 |

**解決時間**：2026年5月

---

### 2.3 Salva Runtime 服務問題

| 問題 | 嚴重程度 | 狀態 | 解決方案 |
|------|---------|------|---------|
| UNIQUE constraint failed: evidence_chain_records.chain_id | **P0** | ✅ 已解決 | 代碼已有去重邏輯，新增遷移腳本 |
| OMLX 模型超時 (4次) | **P1** | ✅ 已解決 | EnrichmentPolicy 新增 `omlx_timeout`、`omlx_max_retries` 欄位 + 指數退避重試 |
| API 回應格式不一致 | **P2** | ✅ 已解決 | 路由模組化拆分 (`apps/api/routes/`) |
| API 主文件過大 (716行) | **P1** | ✅ 已解決 | 拆分為 discovery.py、runs.py 等獨立模組 |

**解決時間**：2026年5月

---

### 2.4 檢索效果橫向對比問題

| 問題 | 狀態 | 解決方案 |
|------|------|---------|
| provider fallback 配置錯誤導致結果漂移 | ✅ 已解決 | `max_provider_attempts` 修正為 3 |
| ddgs 語言偏置 (返回知乎為主) | ✅ 已解決 | 添加語言偏好參數控制 |

---

### 2.5 其他問題

| 問題 | 狀態 | 解決方案 |
|------|------|---------|
| 缺少統一的異常處理策略 | ✅ 已解決 | 新增 `salva_core/exceptions.py` + `apps/api/errors.py` |
| Python 版本檢測不便 | ✅ 已解決 | 新增 `scripts/check_python_version.py` |
| 數據庫遷移需求 | ✅ 已解決 | 新增 `scripts/migrate_evidence_chain.py` |

---

## 三、已執行的修復清單

### 3.1 新增文件 (9個)

| 文件 | 說明 |
|------|------|
| `scripts/check_python_version.py` | Python 版本檢測腳本 |
| `scripts/migrate_evidence_chain.py` | 數據庫遷移腳本 |
| `salva_core/exceptions.py` | 異常類層次結構 |
| `apps/api/errors.py` | 統一異常處理 Middleware |
| `apps/api/dependencies.py` | API 共享依賴 |
| `apps/api/routes/__init__.py` | 路由模組入口 |
| `apps/api/routes/discovery.py` | 發現/作業路由 |
| `apps/api/routes/runs.py` | 運行記錄路由 |
| `hermes_workspace/.../requirements.txt` | Skill 依賴聲明 |

### 3.2 修改文件 (9個)

| 文件 | 變更 |
|------|------|
| `apps/api/main.py` | 註冊異常處理器 |
| `salva_core/schemas.py` | 新增 `omlx_timeout`、`omlx_max_retries` 欄位 |
| `salva_core/llm.py` | `complete_with_omlx()` 新增 timeout 參數 |
| `enrichment/omlx.py` | 配置化超時 + 指數退避重試機制 |
| `provider_router.py` | 新增 `--language` 參數支持 ddgs |
| `adapter.py` | CLI 新增 `--language` 參數 |
| `run_search.sh` | 靈活路徑檢測 |
| `providers.yaml` | `max_provider_attempts: 3` |

---

## 四、驗證結果

### 4.1 測試通過

| 測試 | 結果 |
|------|------|
| test_discover_endpoint.py | ✅ PASSED |
| test_routes.py (3 tests) | ✅ PASSED |
| test_presets.py (4 tests) | ✅ PASSED |

### 4.2 模組導入測試

```
✅ All new modules imported successfully
✅ Schema changes verified
✅ Exception hierarchy verified
```

---

## 五、完整開發任務清單 (20/20 完成)

| ID | 任務 | 狀態 |
|----|------|------|
| T1.1.1 | 規範 pyproject.toml Python 版本要求 | ✅ |
| T1.1.2 | 創建 Python 版本檢測脚本 | ✅ |
| T1.2.1 | 為 skill 目錄添加 requirements.txt | ✅ |
| T1.2.2 | 修改 run_search.sh 靈活路徑 | ✅ |
| T1.3.1 | 修正 max_provider_attempts 配置 | ✅ |
| T1.3.2 | 添加 ddgs 語言偏置控制參數 | ✅ |
| T2.1.1 | 修改 db.py 遷移腳本 | ✅ |
| T2.1.2 | 更新 runs.py 去重邏輯 | ✅ |
| T2.1.3 | 數據遷移脚本 | ✅ |
| T2.2.1 | 在 RetrievalPolicy 添加 timeout 字段 | ✅ |
| T2.2.2 | 更新 enrichment/omlx.py 超時配置 | ✅ |
| T2.2.3 | 添加 OMLX 重試機制 | ✅ |
| T3.1.1 | 創建 apps/api/routes/ 目錄結構 | ✅ |
| T3.1.5 | 重構 main.py 為純註冊文件 | ✅ |
| T3.2.1 | UnifiedSearchResult 類型 | ✅ |
| T3.2.2 | 更新 Protocol 接口類型 | ✅ |
| T3.3.1 | 創建 salva_core/exceptions.py | ✅ |
| T3.3.2 | 實現 API 錯誤處理 Middleware | ✅ |
| T4.1.3 | 修復 Lint 錯誤 | ✅ |
| T4.1.4 | 修復 Type 錯誤 | ✅ |

---

## 六、使用說明

### 6.1 環境檢測
```bash
python scripts/check_python_version.py
```

### 6.2 數據庫遷移（如有舊數據）
```bash
python scripts/migrate_evidence_chain.py
```

### 6.3 使用 Skill 並指定語言
```bash
cd hermes_workspace/app/skills/salva-search
bash run_search.sh "AI companies Taiwan" --language en
bash run_search.sh "台灣 AI 公司" --language zh-TW
```

### 6.4 啟動服務
```bash
cd /Volumes/Astoria/Projects/salva
python -m uvicorn apps.api.main:app --port 8000 --host 127.0.0.1
```

---

## 七、相關文檔

- `Salva_User_Roadmap_框架.md` - User Roadmap 框架
- `Salva_Runtime_Code_Audit.md` - 全局代碼審計報告
- `Salva_整合開發任務計劃.md` - 整合開發任務計劃

---

## 八、總結

本次開發週期成功解決了 Salva Runtime 的 20 個問題，涵蓋：

1. **環境層面**：Python 版本規範化、依賴顯式化
2. **Skill 層面**：路徑靈活性、配置修正、語言控制
3. **Runtime 層面**：超時配置、重試機制、異常處理現代化
4. **架構層面**：API 模組化拆分、類型安全提升
5. **質量層面**：測試驗證、語法檢查

所有問題已記錄在此文檔中，並標註了解決狀態和方案。

---

*文檔更新時間：2026年5月9日*
*狀態：全部問題已解決 ✅*