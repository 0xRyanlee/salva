# Salva Runtime 調用方式效果矩陣測試

> 對比 API/curl、MCP、Skill 三種調用方式的效果差異

## 測試目標

1. **橫向對比**: 同一主題用不同方式調用 → 效果差異
2. **縱向對比**: 不同主題用同一方式調用 → 主題適配性
3. **生成矩陣**: 效果對比表 + 量化指標
4. **優化建議**: 基於數據的改進清單

---

## 三種調用方式說明

| 方式 | 實現方式 | 說明 |
|------|----------|------|
| **API/curl** | 直接 HTTP POST `/v1/discover` | 最直接，無中間層 |
| **MCP** | MCP server 工具 (salva_discover) | 通過 Model Context Protocol |
| **Skill** | OpenClaw skill 包裝 (salva-skill) | 通过 OpenClaw 自動化框架 |

---

## 測試矩陣設計

### 主題選擇 (5個不同領域)

| # | 主題 | Objective | Market | Industry |
|---|------|-----------|--------|----------|
| A | 台灣 AI PM | find_leads | 台灣 | AI人工智慧 |
| B | 美國 FinTech | find_companies | 美國 | FinTech |
| C | 歐洲 AI 論壇 | find_events | 歐洲 | AI人工智慧 |
| D | 全球區塊鏈合作 | find_partnership_signals | 全球 | 區塊鏈 |
| E | 日本電商趨勢 | find_market_activity | 日本 | 電商 |

### 量化指標

| 指標 | 說明 |
|------|------|
| **Raw Count** | 原始檢索結果數 |
| **Qualified Count** | 合格結果數 |
| **Qualified Rate** | 合格率 (Qualified/Raw) |
| **Round Count** | 實際使用輪數 |
| **Latency (ms)** | 响应时间 |
| **Source Diversity** | 來源多樣性 (不同 domain 數) |

---

## 測試矩陣 (5主題 × 3方式 = 15組)

```
              API/curl    MCP        Skill
主題 A        [ ]         [ ]        [ ]
主題 B        [ ]         [ ]        [ ]
主題 C        [ ]         [ ]        [ ]
主題 D        [ ]         [ ]        [ ]
主題 E        [ ]         [ ]        [ ]
```

---

## 預期數據格式

### 每組測試輸出

```json
{
  "test_id": "A-API",
  "topic": "台灣 AI PM",
  "method": "api/curl",
  "metrics": {
    "raw_count": 10,
    "qualified_count": 4,
    "qualified_rate": 0.4,
    "rounds": 3,
    "latency_ms": 4500,
    "source_domains": ["tw.linkedin.com", "www.104.com.tw"]
  },
  "results": [...],
  "issues": []
}
```

---

## 執行順序

### Phase 1: 淺層主題測試 (主題 A, B)

1. A-API → A-MCP → A-Skill
2. B-API → B-MCP → B-Skill

### Phase 2: 中等主題測試 (主題 C, D)

3. C-API → C-MCP → C-Skill
4. D-API → D-MCP → D-Skill

### Phase 3: 深層主題測試 (主題 E)

5. E-API → E-MCP → E-Skill

---

## MCP/Skill 調用方式

### MCP 調用 (如果可用)

```python
# 假設 MCP server 運行在 localhost:8001
# 使用 mcp-client 或直接 HTTP

# 示例通過 mcp-client 調用
result = mcp_client.call_tool("salva_discover", {
    "objective": "find_leads",
    "intent": {
        "market": "台灣",
        "industry": "AI人工智慧"
    },
    "max_results": 10
})
```

### Skill 調用 (通過 OpenClaw)

```bash
# 如果有 salva-skill 配置
/salva discover --objective find_leads --market 台灣 --industry AI
```

---

## 輸出生成

測試完成後生成：

1. **效果矩陣表** (Markdown 表格)
2. **量化分析報告**
3. **問題清單** (含 raw data + 可能原因)
4. **優化建議清單**

---

## 開始執行

要開始執行這個矩陣測試嗎？

執行順序：
1. 主題 A (台灣 AI PM): API → MCP → Skill
2. 主題 B (美國 FinTech): API → MCP → Skill
3. 主題 C (歐洲 AI 論壇): API → MCP → Skill
4. 主題 D (全球區塊鏈): API → MCP → Skill
5. 主題 E (日本電商): API → MCP → Skill