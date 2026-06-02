# Salva Runtime

Salva 是一個自架的 **Discovery Intelligence Runtime** — 面向 Agent、CLI 和 API 調用的結構化檢索服務。

> 它不是爬蟲，而是一個**事件驅動**的智慧 pipeline，可累積學習能力。

---

## 核心定位

- **Event-triggered**：由調用觸發，非定時輪詢
- **API-first**：REST API + MCP + CLI 三端整合
- **Agent-native**：專為 AI Agent 設計的調用介面
- **Compounding**：透過 query-family memory 讓每次檢索比前一次更聰明

---

## Pipeline 運作機制

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Salva Pipeline                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. Intent (調用端)                                                         │
│     ├── objective: find_companies / find_leads / find_events               │
│     ├── market: US / Taiwan / Germany / Japan                              │
│     ├── industry: AI / fintech / gaming                                    │
│     └── extra_keywords, negative_keywords, domain_hints                    │
│                                                                             │
│  ↓                                                                          │
│                                                                             │
│  2. Route Resolution (路由解析)                                             │
│     ├── 選擇 experience_profile: quick_scan / lead_focus / deep_investigation
│     ├── 選擇 retrieval_mode: normal / resilient / wall_guarded             │
│     └── 選擇 strategy: dive / anchor / radar / pirate                       │
│                                                                             │
│  ↓                                                                          │
│                                                                             │
│  3. Query Intelligence (查詢智能)                                          │
│     ├── KeywordGraph: 關鍵詞擴展 (synonym_groups, signal_terms)             │
│     ├── DomainVocab: 領域詞彙註冊 (events / bd_leads / companies)            │
│     └── seed_from_memory: 從歷史成功查詢中注入高分節點                       │
│                                                                             │
│  ↓                                                                          │
│                                                                             │
│  4. Multi-Provider Retrieval (多供應商檢索)                                  │
│     ├── Sequential Fallback: A 失敗 → B → C                                 │
│     ├── Parallel (可選): 同時嘗試多個 provider                              │
│     ├── Adaptive: 根據 provider 歷史響應時間動態調整                       │
│     └── 去重: URL + title 雙重去重                                          │
│                                                                             │
│     Providers:                                                              │
│     ├── SearXNG (首選，本地)                                                 │
│     ├── Whoogle (備選，本地)                                                 │
│     └── DuckDuckGo HTML (公共備用)                                          │
│                                                                             │
│  ↓                                                                          │
│                                                                             │
│  5. Processing (處理)                                                        │
│     ├── Extractor: 從 HTML 提取結構化數據                                    │
│     ├── Deduplicator: fuzzy title + exact URL 去重                         │
│     └── Scorer: qualification score + confidence                             │
│                                                                             │
│  ↓                                                                          │
│                                                                             │
│  6. Enrichment (可選富化)                                                   │
│     ├── OMLX: 本地 LLM 生成的 summary / tags                                │
│     ├── theHarvester: email / host 被動枚舉                                  │
│     ├── Amass: 子網域枚舉                                                   │
│     └── SpiderFoot: OSINT 掃描                                              │
│                                                                             │
│  ↓                                                                          │
│                                                                             │
│  7. Persistence (持久化)                                                   │
│     ├── runs: 完整執行記錄                                                  │
│     ├── entities: CanonicalEntity + evidence                               │
│     ├── relations: 實體關係                                                │
│     ├── hyperedges: 超圖結構                                               │
│     └── query_family_memory: 語義記憶                                        │
│                                                                             │
│  ↓                                                                          │
│                                                                             │
│  8. Output (輸出)                                                            │
│     ├── DiscoveryResponse: entities + relations + telemetry + meta         │
│     ├── JobRecord: 異步 job 追蹤                                            │
│     ├── AuditReport: 品質審計                                               │
│     └── PilotAdvice: 下一步建議                                             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 調用方式

### 1. REST API (同步)

```bash
curl -X POST http://localhost:8000/v1/discover \
  -H "Content-Type: application/json" \
  -d '{
    "objective": "find_companies",
    "intent": {"market": "US", "industry": "AI hardware"},
    "max_results": 10
  }'
```

### 2. REST API (異步)

```bash
# 創建 job，立即返回
curl -X POST http://localhost:8000/v1/jobs \
  -d '{"discovery": {...}, "wait_for_completion": false}'

# 輪詢狀態
curl http://localhost:8000/v1/jobs/{job_id}

# SSE 事件流
curl http://localhost:8000/v1/jobs/{job_id}/stream
```

### 3. CLI

```bash
salva find --market US --industry "AI hardware"
salva job status <job_id>
salva audit <run_id>
salva pilot <run_id>
```

### 4. MCP

```python
# Claude Code / Claude Desktop 配置
{
  "mcpServers": {
    "salva": {
      "command": "python3",
      "args": ["-m", "apps.mcp"]
    }
  }
}

# 調用工具
salva_discover(market="US", industry="AI")
salva_job_create(market="Taiwan", industry="fintech")
salva_audit(run_id="run:xxx")
```

---

## API 端點

| 端點 | 說明 |
|------|------|
| `POST /v1/discover` | 同步 discovery |
| `POST /v1/jobs` | 創建異步 job |
| `GET /v1/jobs/{job_id}` | Job 狀態 |
| `GET /v1/jobs/{job_id}/stream` | SSE 事件流 |
| `GET /v1/runs/{run_id}` | Run 結果 |
| `GET /v1/routes` | 路由目錄 |
| `GET /v1/providers` | 供應商列表 |
| `GET /v1/plugins` | 插件列表 |
| `POST /v1/pilot` | 下一步建議 |
| `POST /v1/audits/{run_id}` | 品質審計 |
| `GET /v1/hold/walk` | 超圖遍歷 |
| `GET /v1/usage` | 用量統計 |

---

## 專案結構

```
salva/
├── apps/
│   ├── api/           # REST API (FastAPI)
│   ├── cli/           # CLI (typer)
│   └── mcp/           # MCP Server
├── core/              # 協調與查詢智能
├── retrieval/         # 供應商適配器
├── processing/        # 提取、去重、評分
├── enrichment/        # LLM/OSINT 富化
├── hold/              # 超圖容器
└── salva_core/
    ├── persistence/  # SQLite 持久化
    ├── schemas.py    # 數據模型
    └── service.py     # 核心服務
```

---

## 快速啟動

```bash
# 1. 安裝
pip install -e ".[dev]"

# 2. 啟動 API
python3 -m uvicorn apps.api.main:app --port 8000

# 3. 測試
curl http://localhost:8000/health
```

---

## 文檔導航

| 文件 | 用途 |
|------|------|
| [CLAUDE.md](CLAUDE.md) | 開發者必讀：設計原則與架構 |
| [TODO.md](TODO.md) | 開發任務清單 |
| [docs/spec/](docs/spec/) | 行為契約 (正式規範) |
| [docs/README.md](docs/README.md) | 文檔索引 |
| [docs/Salva_Runtime_使用者體驗與成熟度審計.md](docs/Salva_Runtime_使用者體驗與成熟度審計.md) | UX 審計 |
| [docs/domain-vocab-guide.md](docs/domain-vocab-guide.md) | 領域詞彙指南 |
| [docs/event-driven-integration.md](docs/event-driven-integration.md) | 整合指南 |
| [docs/sdk.md](docs/sdk.md) | Python SDK |

---

## 錯誤處理

- `400` — 驗證失敗或輸入錯誤
- `403` — Tenant 權限不足
- `404` — 找不到資源
- `429` — Quota 超限
- `500` — 內部錯誤

詳細規範：[docs/spec/error-contract.md](docs/spec/error-contract.md)

---

## 狀態

✅ **v1 完成** — 端到端可用

待優化：
- 錯誤訊息本地化
- 更多 preset
- 向量索引升級 (sqlite-vec)

---

## License

採用 [Apache License 2.0](LICENSE)。允許商用、修改與私有部署,並附帶專利授權;再散布時請保留版權與授權聲明。

Copyright © 2026 Ryan Lee.

---

*更多語言：[English](README.md) | [中文](README.zh.md)*