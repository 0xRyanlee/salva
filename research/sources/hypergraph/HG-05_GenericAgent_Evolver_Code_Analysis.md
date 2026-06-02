---
name: HG-05
description: GenericAgent + Evolver 源碼分析：自我進化 Agent 框架對比研究
tags: [self-evolving, agent, GenericAgent, Evolver, skill-crystallization, GEP, memory-architecture]
created: 2026-04-18
sources: github.com/lsdefine/GenericAgent (3.3k★) | github.com/EvoMap/evolver
---

# HG-05：GenericAgent + Evolver 源碼深度分析

**Ryan 超圖記憶系統第四輪調研**
**日期：2026-04-18**
**重點：微信文章推薦的兩個自我進化 Agent 框架**

---

## 1. 執行摘要

| 框架 | GitHub Stars | 今日之星 | 代碼量 | 定位 | 記憶架構 |
|------|------------|---------|-------|------|---------|
| **GenericAgent** | 3.3k | 848★（同日）| ~3K 行 | 極簡內核 + 技能結晶 | L0-L4 分層記憶 |
| **Evolver** | — | 750★（同日）| Node.js | 基因進化 + 協議約束 | GEP 三元素 |

兩個框架同時登上 2026-04-17 GitHub Trending，代表"讓 Agent 自己學會新技能"的兩條根本路線。

**對 Ryan 超圖記憶系統的核心啟示：**
- GenericAgent 的 L3「技能結晶」機制與 A-Mem 的 Zettelkasten Link Generation 完全吻合
- Evolver 的 GEP 審計日誌（append-only events）可借鑒為超圖記憶的不可變審計層
- 兩者的 WeChat Bot 接口（GenericAgent 支持個人微信）證明 WeChat 作為記憶源的可行性

---

## 2. GenericAgent 源碼深度解析

**Repo:** `lsdefine/GenericAgent` | **License:** MIT | **語言:** Python 95.4%, JavaScript 3.9%

### 2.1 核心數據

| 指標 | 數值 |
|------|------|
| Stars | 3,300 |
| Forks | 362 |
| Commits | 368 |
| Contributors | 14 |
| Agent Loop | ~100 行（`agent_loop.py`）|
| 總代碼量 | ~3,300 行 |
| Token 消耗 | **<30K context**（同類 200K-1M，**6x 節省**）|
| 工具數量 | **9 個原子工具** |
| Bot 接口 | WeChat / QQ / 飛書 / 企業微信 /釘釘 / Qt / Streamlit |

### 2.2 Agent Loop 架構（核心代碼 100行）

**檔案：** `agent_loop.py`（121 行，6.22 KB）

```python
def agent_runner_loop(client, system_prompt, user_input, handler,
                     tools_schema, max_turns=40, verbose=True):
```

**關鍵設計模式：**

```
┌─────────────────────────────────────────────┐
│  StepOutcome Dataclass                      │
│  data / next_prompt / should_exit           │
├─────────────────────────────────────────────┤
│  BaseHandler（工具分發 + 回調鉤子）         │
│  tool_before_callback → do_{tool} →        │
│  tool_after_callback                        │
├─────────────────────────────────────────────┤
│  Generator-based Architecture               │
│  函數 yield 進度，支持流式輸出             │
├─────────────────────────────────────────────┤
│  Context 優化：每 10 輪重置工具描述        │
│  → 防止 context膨脹（6x token 節省關鍵）  │
└─────────────────────────────────────────────┘
```

**退出條件：**
| 條件 | 退出原因 |
|------|---------|
| `outcome.should_exit = True` | `EXITED` |
| `outcome.next_prompt = None` | `CURRENT_TASK_DONE` |
| 超過 `max_turns` | `MAX_TURNS_EXCEEDED` |

**代碼收縮策略（防止 context overflow）：**
```python
def _clean_content(text):
    # 超過 6 行的代碼區塊壓縮為行數預覽
    # "```python\n[50 lines]\n" → "```python [50 lines only showing first and last]"
```

### 2.3 九個原子工具

| 工具名 | 函數 | 說明 |
|--------|------|------|
| `code_run` | 執行任意代碼 | 核心執行器 |
| `file_read` | 讀取文件 | — |
| `file_write` | 寫入文件 | — |
| `file_patch` | 精確修改文件 | 類似 patch |
| `web_scan` | 感知網頁內容 | 爬取+視覺 |
| `web_execute_js` | 控制瀏覽器行為 | 保持登錄 session |
| `ask_user` | 人類確認 | human-in-the-loop |
| `update_working_checkpoint` | 更新工作檢查點 | 記憶工具 |
| `start_long_term_update` | 啟動長期更新 | 記憶工具 |

**工具調度模式（Handler Pattern）：**
```python
def dispatch(self, tool_name, args, response, index=0):
    method_name = f"do_{tool_name}"
    if hasattr(self, method_name):
        # tool_before_callback → do_{tool_name} → tool_after_callback
```

### 2.4 L0–L4 分層記憶系統（最核心創新）

**記憶目錄結構：**
```
memory/
├── L4_raw_sessions/              # 原始對話存檔
├── autonomous_operation_sop/      # 自主操作 SOP
├── skill_search/                  # 技能搜索
├── adb_ui.py                      # Android 調試橋 UI
├── keychain.py                    # 敏感數據存儲
├── ljqCtrl.py                     # 控制模塊
├── ocr_utils.py                   # OCR 工具
├── procmem_scanner.py            # 進程內存掃描
├── ui_detect.py                   # UI 元素檢測
└── *.md (SOP 文檔)               # 13 份標準操作程序
```

**L0–L4 分層職責：**

| 層 | 名稱 | 目的 | 內容類型 |
|----|------|------|---------|
| **L0** | Meta Rules | 行為約束，相當於「憲法」 | 硬性規則，不可覆蓋 |
| **L1** | Insight Index | 快速路由，判斷調用哪個技能 | 關鍵詞索引、意圖路由 |
| **L2** | Global Facts | 長期積累的穩定知識 | 事實庫、偏好、背景 |
| **L3** | Task Skills / SOPs | **可復用的工作流結晶** | 技能/SOP，可直接調用 |
| **L4** | Session Archive | 每次任務的精華摘要 | 歸檔記錄，長期召回 |

### 2.5 技能結晶機制（Core Innovation）

**與 A-Mem Zettelkasten 的對比：**

| 維度 | GenericAgent | A-Mem |
|------|-------------|-------|
| 基本單元 | 技能/SOP | Note |
| 建立觸發 | 任務完成後自動結晶 | 對話結束後自動建立 |
| 連結方式 | L1 Insight Index 路由 | LLM 判斷有意義連結 |
| 演化 | 新任務觸發更新 | 新記憶觸發現有記憶演化 |
| 層次 | L0-L4（5層） | Note+Link（2層）|

**技能結晶流程：**
```
新任務來了
  ↓
自主探索（安裝依賴、寫腳本、調試驗證）
  ↓
解決過程完成
  ↓
自動「結晶」成可復用技能
  ↓
寫入 L3（Task Skills / SOPs）
  ↓
下次類似任務 → 直接調用技能
```

**實例（從 README）：**

| 任務 | 第一次 | 之後 |
|------|--------|------|
| 讀取微信消息 | 安裝依賴→逆向量 DB→寫腳本→保存技能 | **一行調用** |
| 監控股票提醒 | 安裝 mootdx→構建流程→配置 cron→保存技能 | **直接啟動** |
| 發送 Gmail 附件 | 配置 OAuth→寫發送腳本→保存技能 | **隨時可用** |

### 2.6 上下文消耗優化

**對比同類框架：**

| 框架 | Context 消耗 |
|------|------------|
| GenericAgent | **<30K** |
| Claude Code | 200K-1M |
| OpenClaw | 高（530K 行代碼）|

**節省策略：**
1. 每 10 輪重置工具描述（`client.last_tools = ''`）
2. 代碼區塊超過 6 行自動收縮為行數預覽
3. L1 Insight Index 提供快速路由，減少無效 context 注入

### 2.7 Bot 接口矩陣

GenericAgent 的多平台支持，Ryan 的 WeChat 接口完全吻合：

| 平台 | 狀態 | 套件 |
|------|------|------|
| **WeChat（個人）** | ✅ 可用 | `pycryptodome qrcode requests` |
| QQ Bot | ✅ 可用 | `qq-botpy` |
| 飛書 | ✅ 可用 | `lark-oapi` |
| 企業微信 | ✅ 可用 | `wecom_aibot_sdk` |
| 釘釘 | ✅ 可用 | `dingtalk-stream` |
| Qt Desktop | ✅ 可用 | `pywebview` |
| Streamlit | ✅ 可用 | `streamlit` |

### 2.8 與 OpenClaw / Claude Code 橫向對比

| 特徵 | GenericAgent | OpenClaw | Claude Code |
|------|:---:|:---:|:---:|
| 代碼量 | **~3K** | ~530K | 大型 |
| 部署 | `pip install` + API Key | 多服務 | CLI + 訂閱 |
| 瀏覽器控制 | 保持 session 的真實瀏覽器 | 沙箱/headless | MCP 插件 |
| OS 控制 | 鼠標/鍵盤/視覺/ADB | 多 Agent | 文件+終端 |
| 自我進化 | **自主技能生長** | 插件生態 | 無狀態 |
| Token 效率 | **<30K（6x 節省）** | 高 | 中 |
| 進化方向 | 分布式（每個實例獨特） | 生態（共享）| — |

---

## 3. Evolver（GEP 協議）源碼深度解析

**Repo:** `EvoMap/evolver` | **License:** GPL-3.0 | **語言:** Node.js >= 18

### 3.1 核心定位

```
Evolver = 提示詞生成器，不是代碼修補器
每次進化循環：
  1. 掃描 memory/ 目錄中的日誌
  2. 提取錯誤模式和優化信號
  3. 從基因庫匹配基因
  4. 生成 GEP 合規提示詞
  5. 記錄 EvolutionEvent（不可篡改審計日誌）
  ↓
  所有實際代碼修改由宿主運行時解釋執行
```

### 3.2 GEP 協議三元素

```
assets/gep/
├── genes.json      # 進化基因定義
├── capsules.json   # 可復用能力膠囊
└── events.jsonl    # 所有進化的不可篡改審計日誌
```

#### 3.2.1 Gene（基因）

**定義：** 一條提示詞修改策略 = 一個基因

```json
{
  "gene_id": "api_timeout_cache_fallback",
  "trigger": "當 Agent 遇到 API 超時",
  "action": "自動切換到緩存模式",
  "validation": "node test_api_cache.js",
  "capsule": "error_recovery"
}
```

**基因示例：**
- 「當 API 超時時，自動切換緩存模式」
- 「當錯誤率超過 5% 時，觸發降級方案」

#### 3.2.2 Capsule（膠囊）

**定義：** 多個相關基因打包在一起

```json
{
  "capsule_id": "error_recovery",
  "name": "錯誤恢復膠囊",
  "genes": [
    "api_timeout_cache_fallback",
    "retry_with_exponential_backoff",
    "degrade_to_basic_mode"
  ]
}
```

#### 3.2.3 EvolutionEvent（進化事件）

**定義：** 每次基因被選中並應用的完整記錄

```jsonl
{"event_id": "...", "parent_id": "...", "gene_id": "...", "trigger_signal": "...", "validation_result": "...", "timestamp": "..."}
```

**關鍵特性：**
- **不可篡改**（append-only）
- **樹狀結構**（透過 `parent_id` 關聯）
- **完整血統可追溯**

### 3.3 四種策略模式

| 策略 | 創新 | 優化 | 修復 | 適用場景 |
|------|------|------|------|---------|
| `balanced`（默認）| 50% | 30% | 20% | 日常運行，穩定增長 |
| `innovate` | **80%** | 15% | 5% | 系統穩定，快速探索新功能 |
| `harden` | 20% | 40% | **40%** | 大改動後，收斂優先 |
| `repair-only` | 0% | 20% | **80%** | 緊急狀態，全力修 bug |

**對比軟體工程團隊：**
- `balanced` = 正常 sprint
- `innovate` = 創新衝刺
- `harden` = 發布前穩定化
- `repair-only` = 緊急 hotfix

### 3.4 三種運行模式

| 模式 | 命令 | 行為 |
|------|------|------|
| **Standalone** | `node index.js` | 生成提示詞，輸出到 stdout，退出 |
| **Loop** | `node index.js --loop` | 守護進程循環，自適應睡眠 |
| **Review** | `node index.js --review` | 人類審批後每步才執行 |

### 3.5 進化生命週期

```
┌─────────────────────────────────────────────┐
│ Phase 1: Signal Extraction（信號提取）        │
│  - 自動掃描 memory/ 中的日誌                 │
│  - 識別錯誤、崩潰、優化模式                 │
├─────────────────────────────────────────────┤
│ Phase 2: Asset Selection（資產選擇）         │
│  - 根據信號匹配評分基因/膠囊                │
│  - 代碼：src/gep/selector.js               │
├─────────────────────────────────────────────┤
│ Phase 3: Prompt Generation（提示詞生成）      │
│  - 發出 GEP 合規提示詞                      │
│  - 包含約束、策略、驗證要求                 │
│  - 代碼：src/gep/prompt.js                 │
├─────────────────────────────────────────────┤
│ Phase 4: Solidify（固化可選）               │
│  - src/gep/solidify.js 執行驗證命令        │
│  - Git 提交，記錄 EvolutionEvent            │
└─────────────────────────────────────────────┘
```

### 3.6 安全模型

**執行邊界（關鍵設計）：**

| 組件 | 執行 Shell 命令？ |
|------|-----------------|
| `src/evolve.js` | ❌ 只讀 git/process 查詢 |
| `src/gep/prompt.js` | ❌ 純文本生成 |
| `src/gep/selector.js` | ❌ 純邏輯 |
| `src/gep/solidify.js` | ✅ 僅驗證過的命令 |

**驗證命令白名單：**
```javascript
// 只允許：
node, npm, npx
// 阻擋：
$(...), ;, &, |, >, <, cwd
```

**額外安全機制：**
- Git 回滾（任意進化可撤銷）
- 影響範圍計算（blast radius calculation）
- `sessions_spawn(...)` 輸出到 stdout，不是可執行代碼

### 3.7 EvoMap 網絡協作

**定位：** 進化資產的協作網絡

| 功能 | 說明 |
|------|------|
| Skill Store | 下載/發布可復用技能 |
| Worker Pool | 接收網絡進化任務 |
| Evolution Circle | 協作進化小組 |
| Asset Publishing | 與網絡共享基因/膠囊 |

**離線運行：** 完全不需要 `.env` 配置，Hub 連接僅用於網絡功能。

---

## 4. 兩框架深度對比

### 4.1 進化模式對比

| 維度 | GenericAgent | Evolver |
|------|-------------|---------|
| **進化類型** | 分布式（從每次任務執行中自然湧現）| 集中式（有明確進化引擎管理）|
| **技能載體** | L3 Task Skills / SOPs | Genes / Capsules |
| **觸發方式** | 任務完成 → 自動結晶 | 日誌信號 → 基因匹配 |
| **驗證機制** | Agent 自主驗證 | 協議約束 + 命令白名單 |
| **記憶持久化** | L0-L4 分層（5層）| GEP events.jsonl（append-only）|
| **個性化程度** | 每個實例長出獨一無二的技能樹 | 共享基因庫，適合團隊協作 |

**比喻：**
- GenericAgent = 野蠻生長（每個實例因使用場景不同而獨特）
- Evolver = 精心育種（集中管理、可審計、可回滾）

### 4.2 記憶架構對比

| 維度 | GenericAgent | Evolver | A-Mem | Ryan Hypergraph |
|------|-------------|---------|-------|----------------|
| **層次** | L0-L4（5層）| — | Note+Link | Vertex+Hyperedge |
| **索引** | L1 Insight Index | genes.json | Top-k embedding | Jina embedding |
| **事實存儲** | L2 Global Facts | — | — | Vertex attributes |
| **技能/流程** | L3 SOPs | Genes/Capsules | Linked notes | Hyperedges |
| **會話存檔** | L4 Raw Sessions | events.jsonl | — | Session vertices |
| **不可變日誌** | — | ✅ events.jsonl | — | 可擴展屬性 |
| **演化機制** | 自動結晶 | 基因匹配+驗證 | Memory Evolution | Hyperedge merging |

### 4.3 上下文效率對比

| 框架 | Context 消耗 | Token 節省幅度 |
|------|------------|--------------|
| GenericAgent | <30K | 基準 |
| Claude Code | 200K-1M | 6x+ 更多 |
| OpenClaw | 高 | — |
| MemGPT | 極大 | — |

### 4.4 企業 vs 個人定位

| 維度 | GenericAgent（個人）| Evolver（企業）|
|------|------------------|--------------|
| 目標用戶 | 獨立開發者 | 工程團隊 |
| 可追溯性 | 低（本地生長）| 高（GEP 審計日誌）|
| 協作 | 無（分布式）| 有（EvoMap 網絡）|
| 變更控制 | 分散 | 集中審批 |
| 安全要求 | 個人設備 | 企業合規 |
| 適用場景 | 日常任務自動化 | Agent 規模化管理 |

---

## 5. 對 Ryan 超圖記憶系統的借鑒意義

### 5.1 GenericAgent 帶來的啟示

**1. L3 技能結晶 → Ryan 超圖的超邊設計**

```
GenericAgent 的 L3 = 技能/SOP = Ryan 系統的 Hyperedge

GenericAgent 的結晶觸發：
  任務完成 → 探索過程 → 結晶為 SOP

Ryan 系統的超邊建立：
  對話完成 → 提取實體 → 建立 n-ary 超邊

兩者在本質上相同：將經驗封裝為可復用單元
```

**2. L1 Insight Index → Ryan 系統的 Jina 路由層**

```
GenericAgent L1：快速路由到正確的 L3 技能
Ryan 系統：Jina embedding 找到相關頂點/超邊

作用相同：避免每次都遍歷全部記憶
```

**3. 上下文優化 → Ryan 系統的 Phase 1 目標**

GenericAgent 的 6x token 節省 = 每 10 輪重置工具描述 + 代碼區塊收縮

Ryan 系統的目標：
- L1 精準路由（減少無效 context）
- 每次對話限制注入頂點數量
- 超邊查詢結果自動摘要

**4. WeChat Bot 接口 → Ryan 系統的輸入源驗證**

GenericAgent 支持個人微信作為 Bot 前端。

Ryan 系統：
- WeChat 對話 = 記憶攝入源（目前領先所有競品）
- WeChat 消息 → 自動建立 Hyperedge（待實現）

### 5.2 Evolver 帶來的啟示

**1. GEP EvolutionEvent → Ryan 超圖的審計層**

```
Evolver 的 append-only events.jsonl：
  - 每次進化有完整血統
  - 不可篡改
  - 可追溯

Ryan 系統的 Hyperedge 可加入 audit trail：
  hyperedge.attrs["evolution_events"] = [...]
  - 何時建立
  - 何種觸發
  - 驗證結果
```

**2. 四種策略模式 → Ryan 系統的進化觸發**

| Evolver 策略 | Ryan 系統對應 |
|-------------|--------------|
| `balanced` | 每日 cron 正常生長 |
| `innovate` | 主題研究模式（擴展新領域）|
| `harden` | 大改動後（驗證已有超邊一致性）|
| `repair-only` | 發現矛盾時（觸發事實修正）|

**3. 基因選擇器 → Ryan 系統的超邊匹配**

```
Evolver: src/gep/selector.js
  - 根據信號評分基因
  - 選擇最合適的基因應用

Ryan: expand_via_hypergraph(v, depth=2)
  - 根據查詢意圖匹配超邊
  - 擴展找到所有相關節點
```

**4. 命令白名單 → Ryan 系統的安全邊界**

Evolver 只允許 `node`, `npm`, `npx`。

Ryan 系統應該：
- 對 Obsidian vault 的寫入操作需要明確確認
- 避免自動刪除頂點/超邊（append-only 或 soft-delete）

### 5.3 兩個框架的互補應用

```
GenericAgent 的分布式技能生長
  ↓ 提供 Ryan 系統的「技能獲取」層
Evolver 的集中審計追蹤
  ↓ 提供 Ryan 系統的「演化控制」層

Ryan 超圖記憶系統的完整進化循環：
  1. GenericAgent 式：WeChat 對話 → 自動建立 Hyperedge（技能結晶）
  2. Evolver 式：超邊變更 → append-only audit log（可控可追溯）
  3. A-Mem 式：定期內省 → Hyperedge Merging（記憶演化）
  4. OMEGA 式：Intelligent Forgetting → 清理低價值超邊（長期維護）
```

---

## 6. 代碼層級的具體差異

### 6.1 架構哲學

| 維度 | GenericAgent | Evolver |
|------|-------------|---------|
| 代碼行數 | ~3K | Node.js（約 1K）|
| 架構哲學 | 極簡內核 + 无限生长 | 協議約束 + 明確邊界 |
| 進化觸發 | 被動（任務完成自動結晶）| 主動（日誌掃描+基因匹配）|
| 驗證方式 | Agent 自主判斷 | 命令白名單 + Git 回滾 |
| 語言 | Python | Node.js |

### 6.2 記憶組織

| 維度 | GenericAgent | Evolver |
|------|-------------|---------|
| 存儲格式 | Markdown（SOP）+ Python 結構 | JSON（genes.jsonl）|
| 索引方式 | L1 Insight Index（關鍵詞路由）| 基因評分（selector.js）|
| 不可變日誌 | — | events.jsonl |
| 持久化 | 文件系統 | 文件系統 + Git |

### 6.3 安全假設

| 維度 | GenericAgent | Evolver |
|------|-------------|---------|
| 執行假設 | Agent 完全可信 | 協議約束 + 命令白名單 |
| 進化邊界 | 無硬性邊界 | 明確的安全模型 |
| 人類控制 | 可選（ask_user）| Review 模式 |

---

## 7. 對 Ryan 系統的具體行動建議

### 7.1 短期（立即可實現）

| 來源的具體功能 | 借鑒到 Ryan 系統 |
|--------------|----------------|
| GenericAgent 的 `_clean_content` 策略 | 限制單次注入超邊/頂點數量 |
| GenericAgent 每 10 輪重置工具描述 | 限制 Hypergraph-DB 查詢深度 |
| GenericAgent 的 L1 Insight Index | 用 Jina embedding 做頂點預篩選 |

### 7.2 中期（Phase 2-3）

| 來源的具體功能 | 借鑒到 Ryan 系統 |
|--------------|----------------|
| GenericAgent 的 L3 技能結晶 | 實現 Hyperedge 的自動建立邏輯 |
| Evolver 的 events.jsonl | 為 Hyperedge 建立 append-only audit trail |
| Evolver 的四種策略模式 | 實現超圖記憶的 growth/maintenance/repair 策略 |

### 7.3 長期（Phase 4）

| 來源的具體功能 | 借鑒到 Ryan 系統 |
|--------------|----------------|
| GenericAgent 的分布式進化 | 每個用戶的 Hypergraph 獨立生長 |
| Evolver 的 EvoMap 網絡 | 跨用戶共享 Hyperedge 模板（可選）|
| OMEGA 的 Intelligent Forgetting | 自動超邊清理 + 等級制度 |

---

## 8. 補充調研：微信生態 Agent 現況

### 8.1 GenericAgent WeChat Bot 實作

```python
# frontends/wechatapp.py
pip install pycryptodome qrcode requests
python frontends/wechatapp.py
```

**原理：** 個人微信號作為 Bot 接口（Webot 協議）

**對 Ryan 的意義：**
- Ryan 系統目前的 WeChat 集成 = Hermes gateway
- GenericAgent 證明 WeChat 可作為可靠的 Agent 接口
- 兩者結合：Hermes（通信層）+ GenericAgent（技能生長）+ Ryan Hypergraph（記憶引擎）

### 8.2 相關開源生態

| 項目 | 語言 | 功能 |
|------|------|------|
| `lsdefine/GenericAgent` | Python | 3K 行技能結晶 |
| `EvoMap/evolver` | Node.js | GEP 基因進化 |
| `modelscope/AgentEvolver` | — | 統一 self-questioning/navigating/attributing |
| `XMUDeepLIT/Awesome-Self-Evolving-Agents` | — | 自進化 Agent 資源匯總 |

---

## 9. 結論

### 9.1 核心發現

1. **GenericAgent 證明了「技能結晶」機制的工程可行性**
   - 3000 行代碼支撐 6x token 節省
   - L0-L4 分層記憶是可複製的架構
   - WeChat 接口已驗證

2. **Evolver 證明了「協議約束進化」的企業價值**
   - GEP 三元素（Gene/Capsule/Event）是可借鑒的抽象
   - 審計日誌不可篡改是安全底線
   - 四種策略模式覆蓋常見場景

3. **兩個框架共同指向一個方向：Agent 的能力邊界不應由開發者預定義**
   - GenericAgent = 從實例使用中湧現
   - Evolver = 從共享基因庫中獲取

### 9.2 Ryan 系統的差異化定位

```
GenericAgent 的擅長：極簡內核、分布式技能生長、個人場景
Evolver 的擅長：集中審計、企業合規、團隊協作

Ryan 系統的擅長：
  - 超圖結構（原生 n-ary 關係，比兩者都更強）
  - WeChat 對話整合（GenericAgent 驗證可行）
  - 本地優先（結合 OMEGA 的 Intelligent Forgetting）
  - 中文優先（兩者均無明確支持）

結論：
  Ryan 超圖記憶系統 = GenericAgent 的技能結晶
                             + Evolver 的審計追蹤
                             + OMEGA 的工程品質
                             + HyperGraphRAG 的理論基礎
```

---

## 參考文獻

### GenericAgent 生態
1. `lsdefine/GenericAgent` — GitHub 3.3k★，MIT License
2. `agent_loop.py` — 121 行核心 Agent 循環
3. `memory/` 目錄 — L0-L4 分層記憶實現
4. `frontends/wechatapp.py` — WeChat Bot 接口

### Evolver 生態
5. `EvoMap/evolver` — GitHub，GPL-3.0 License
6. `src/gep/genes.json` — 進化基因定義
7. `src/gep/selector.js` — 基因評分選擇器
8. `src/gep/prompt.js` — GEP 提示詞生成
9. `evomap-evolver.mintlify.app` — 官方文檔

### 相關自進化 Agent
10. `modelscope/AgentEvolver` — 端到端自進化框架
11. `XMUDeepLIT/Awesome-Self-Evolving-Agents` — 自進化 Agent 資源大全

---

標籤：#GenericAgent #Evolver #GEP #self-evolving #skill-crystallization #agent-memory #code-analysis #wechat
