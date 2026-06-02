# 記憶系統架構調研

**Date:** 2026-04-18
**Status:** Completed

---

## 現存三套記憶系統對比

| 維度 | Hermes (Agent) | Obsidian (Ryan/iCloud) | BDDB (專案SQLite) |
|------|---------------|------------------------|------------------|
| **位置** | `~/.hermes/memories/` | `~/Library/Mobile Documents/iCloud~md~obsidian/` | `~/Desktop/bddb/backend/state/` |
| **同步** | 本地，無多設備 | iCloud 自動同步 | Git/本地 |
| **格式** | 純 Markdown（MEMORY.md / USER.md）| Markdown + Dataview + TableEditor | SQLite schema |
| **更新方式** | `memory` tool（add/replace/remove）| 手動編輯 + plugins | FastAPI 寫入 |
| **用途** | Agent 系統偏好、Ryan 人物誌 | Ryan 工作日誌、研究筆記、作戰規劃 | BD leads 追蹤 |
| **組織** | 2 個大檔（system/user）| vault 結構（ryan/memory/research/bd/plans/tasks）| 5 張表 |
| **Plugins** | N/A | Dataview, TableEditor, Mermaid, Markmind | N/A |

---

## 缺口分析

### 1. Hermes 記憶太薄
- `MEMORY.md` 只有 17 行（系統偏好）
- `USER.md` 只有 16 行（Ryan 人物誌）
- 缺乏結構：沒有 topics/people/context 分層，所有東西塞在同一個檔

### 2. Obsidian 是 Ryan 的真正知識庫
- 有完整的 vault 結構：`ryan/`（求職）、`research/`（研究）、`memory/`（系統）、`bd/`（商務）
- 有 21 份 2026-03-21 研究報告的痕跡
- iCloud 同步，可跨設備

### 3. BDDB 與其他系統脫鉤
- 就是 5 張 SQL 表，無知识图谱
- 跟 Hermes/Obsidian 完全隔離

---

## 建議方向

- 統一 vault 結構：確定 `memory/topics/` 和 `memory/people/` 是存放「固化知識」的地方
- Hermes 的 `MEMORY.md` 可以變成一個 index pointer，指向 Obsidian vault 的對應實體
- 超圖 skill 的 output 最終寫入 `workspace/research/hypergraph/` 這個 vault 路徑

---

## 相關檔

- `~/.hermes/memories/MEMORY.md` — Hermes 系統偏好
- `~/.hermes/memories/USER.md` — Ryan 人物誌
- `~/Desktop/bddb/SPEC.md` — BDDB 規格
