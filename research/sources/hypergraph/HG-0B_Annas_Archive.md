# 安娜的檔案 (Anna's Archive)

**URL:** annas-archive.gl / annas-archive.pk / annas-archive.vg / annas-archive.gd
**Status:** 活躍（2026-01 遭美國法院永久禁令，禁止 WorldCat 數據）

---

## 基本資訊

| 項目 | 內容 |
|------|------|
| **網站類型** | 搜索引擎、數位圖書館、檔案分享 |
| **創始人** | 安娜和/或盜版圖書館鏡像團隊（匿名）|
| **推出時間** | 2022年11月10日 |
| **非營利** | 是，接受捐款 |

---

## 規模統計（截至2023年11月）

| 類型 | 數量 |
|------|------|
| 書籍 | 22,052,322 本 |
| 文章 | 97,847,390 篇 |
| 漫畫 | 2,451,032 本 |
| 雜誌 | 673,013 本 |

---

## 核心定位

- **非營利組織**，本身**沒有儲存任何侵權作品**
- 只儲存公眾能在其他途徑獲得的**元數據**
- 轉錄源自**開放圖書館**的元數據
- 備份 Z-Library、Library Genesis、Sci-Hub 三大影子圖書館
- 提供**國際標準書號**資訊

---

## 重要事件

| 日期 | 事件 |
|------|------|
| 2022-11 | 美國當局查封 Z-Library後，團隊決定創立 Anna's Archive |
| 2023-10 | 成功抓取 WorldCat 數據，去重後共 **7億條記錄** |
| 2023-11 | 獲得匿名人士捐贈的 750萬本中文圖書資源（約 350TB）|
| 2024-02 | WorldCat 運營方 OCLC 起訴 Anna's Archive |
| 2026-01-16 | 美國俄亥俄州南區聯邦地方法院法官 Michael Watson 作出缺席判決，要求永久刪除 WorldCat 數據 |

---

## 宗旨

> 「**資訊渴望自由**（Information wants to be free）」

- 「站在 Z-Library 等相關網站的對立面——盡可能不會留下任何蹤跡，有很高的作業安全意識」
- 「數據和代碼都是**開源**的，因此可以**無限地東山再起**」

---

## 相關論文/技術

- Anna 專案的記憶系統架構（`github.com/vaayne/anna`）：
  - **LCM Plugin (Lossless Context Management)**：DAG 結構的摘要壓縮
  - **Simple Plugin**：滑動窗口，無摘要
  - 6 張 SQLite 表：`ctx_conversations / ctx_messages / ctx_summaries / ctx_items / ctx_summary_messages / ctx_summary_parents`
  - 7 個可選 interface：`Compactor / Searcher / Explorer / ProfileStore / SessionManager / ReviewSource`

---

## 標籤

#影子圖書館 #元搜索引擎 #數位圖書館 #信息自由 #開放知識
