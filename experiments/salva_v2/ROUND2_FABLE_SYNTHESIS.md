# Round 2 — Fable 獨立終局綜合分析：根因鏈、資料流形、超圖架構、多維修法

**日期**：2026-07-24。輸入：`ROUND2_FINDINGS.md`、`EXPERIMENT_PROTOCOL_ROUND2.md`、
`hg_penetration/README.md`+`E9_FINDINGS.md`、`CONFIDENCE_REBUILD_FINDINGS.md`、
`core/controller.py`/`salva_core/service.py` 現況代碼。

沿用 fable 在協定設計階段（`EXPERIMENT_PROTOCOL_ROUND2.md` 開頭修訂記錄）已證明的
獨立視角可信度，這是同一位審視者對執行完的結果做的終局分析，非本 session 主線
自己下的結論。

---

## 1. 根因鏈：一個設計承諾的多層表徵 + 真實的層間疊加

```
[根因 R0] Salva 的 pipeline 是「域內廣收型」設計：
  模板化 query（primary×role×region×signal 組合）+ 固定策略輪替 + 統計性收斂判準
  （core/query_strategy.py:205-328、core/controller.py:196-245）
    │
    ├─→ [表徵1：retrieval 層] query 模板把目標實體名稀釋進行業詞彙組合，
    │    task intent 裡的 "official website"/"contact" 被當成獨立 primary node
    │    後被 primaries[:2] 截斷丟棄（query_strategy.py:212）
    │    → 83% GT 不進 raw pool、8/15 連網域都沒摸到
    │
    ├─→ [表徵2：scoring 層] scorer 為 events/leads 詞彙手調，對「官方頁面」
    │    這類 GT 沒有訊號 → Round 1 的 61% zero-qualified
    │
    └─→ [表徵3：selection 層] gate 用閾值二值化 admit → 0 產出
         （已被 confidence.py + rank 修掉：3/3 轉換、0 regression）
```

用數字拆解：`recall_admitted = recall_all（retrieval 天花板）× selection 轉換率`。
Round 2 天花板是 3/18≈0.167，Arm F 拿到 0.122——**selection 層在有料的任務上已
接近打滿**。三層病灶獨立但同源：pipeline 最佳化目標（探索一個 domain 下的多實體）
跟 benchmark 任務（收斂到單一精確事實）結構性錯位。這也是 bare Haiku 3.28 次搜尋
拿 0.499 的原因：它是目標條件化閉環（搜→看→改寫→驗證），Salva 是開環模板
（telemetry 回饋只做統計性關鍵詞吸收，沒有「還缺什麼事實」的概念）。

佐證：`single-01-tsmc` 整個 run 的 raw pool 只有 4 筆，Salva 動作更多、拿回來的
東西反而更少更歪。

## 2. 資料流形分析：最嚴重壓縮發生在「頁面↔實體 1:1 錨定」

按資訊損失嚴重度排序：

1. **（最嚴重）`salva_core/legacy.py:37-87,143-145`**：`legacy_result_to_entity`
   是 1 result → 1 entity，`entity_id = md5(source_name:source_url)`——**Salva
   的「實體」本體論其實是「網頁」，不是世界中的公司/人/事件**。一張列了 20 個
   合作夥伴的頁面被投影成 1 個 `activity_signal` 實體。這是不可逆的維度塌縮，
   下游一切問題連鎖於此：entity_resolution 的 null 不是意外——兩個講同一家公司
   的頁面 URL 不同 → entity_id 不同，天生無料可合。
2. **（次嚴重）`legacy.py:90-118`**：relation 只有兩種硬編碼二元邊
   （`hosted_by`/`has_contact`）。partnership/customers 這類 multihop GT 的
   n-ary 事實**在 schema 上沒有落點**——不是被壓縮，是根本沒有表示空間。
3. **（第三）`core/controller.py:249-263`**：全池按單一 confidence 純量切
   top-K，無多樣性/facet 結構。相對前兩點這層已被部分修復（corroboration 本身
   就是把「retrieval 過程的多維佐證」重新注回純量，且有效）。
4. **（提醒）`runs.py:539-618` 的 `_derive_default_hyperedges`**：只產兩種
   裝飾性 hyperedge（`entity_bundle`/`query_family`）——有 n 元形式、沒有 n 元
   語意。真正的 n-ary 域事實從未被寫入。

## 3. 超圖架構修正提醒

**「已驗證但束之高閣」確實是架構問題，但缺的不是接線、是中間那一級。**
hg_penetration 的 hyperedge 是從結構化來源（SEC 13D cover pages）抽出來的；
live pipeline 的中間產物是頁面級 UnifiedResult，**缺一個「頁面→n-ary 事實」的
抽取級**，`_derive_default_hyperedges` 的裝飾性產物就是這個缺口的症狀——實驗
驗證了表示層，但 live pipeline 的資料流形在更上游就已經塌縮（見第 2 點），
表示層無處安放。

**最小侵入接點（具體）**：`persist_discovery_run` 簽名**已經**接受
`hyperedges: list[HoldHyperedgeRecord] | None`（`runs.py:45`），只在 None 時
才 fallback 到 `_derive_default_hyperedges`（`runs.py:219`）。最小改動：在
`service.py::execute_discovery` 算 `relations = _collect_relations(results)`
的位置（`service.py:186`），加一個 n-ary 事實抽取步驟，產出真
`HoldHyperedgeRecord`，經 `run_discovery`（`service.py:112`）傳進
`persist_discovery_run(hyperedges=...)`。**持久層零改動。**

**multihop tier 與 hyperedge 的關聯——誠實版**：兩件事有關但不是同一件事。
multihop recall 最差的直接原因是 retrieval（GT 頁面根本沒被抓到），接 hyperedge
救不了它。但 multihop/partnership 任務的 GT 本質上就是 n-ary 關係事實，現在的
頁面本體論連正確表示它都做不到。**正確順序是依賴鏈，不是替代方案**：
hyperedge 是 multihop tier 的正確目標表示（也是 Salva 相對 bare agent 唯一已
被實證的差異化），但前置條件是先修 retrieval + 加抽取級。

## 4. 各維度卡點與修法（含優先序）

**4a. 檢索/資料獲取（最高槓桿——83% 天花板在這裡）**
1. P0 實體錨定 query 模式：intent 含具名實體時，round 1 應組
   `"<實體名>" official website`/`"<實體名>" contact`，而非現在
   `primaries[:2]` 截斷丟棄 "official website"/"contact"（`query_strategy.py:212-254`）。
2. P0 域名鎖定升級（closed loop）：一旦命中疑似官方網域，下一輪對缺失 facet
   發 `site:<domain>` 查詢。掛點：`enable_query_proposal` 已在 controller
   （`controller.py:254,280-337`）但 `execute_discovery` 從沒傳它（`service.py:239-247`
   註解自承不可達）——接通並擴成「缺什麼補什麼」。
3. P1 第二 provider：目前 fixture 只有 ddgs，corroboration 的
   provider-diversity 軸實作了但退化。
4. P1 任務級成功判準取代統計收斂：`controller.py:238-245` 的 convergence 是
   統計量，跟「任務答完了沒」無關——這是 Salva 與 bare agent 行為差距的機制核心。

**4b. 排序/篩選**
1. P0（最便宜）預設 `admission_policy` 切到 rank：3/3 轉換、0 regression。先補
   precision@K 量化。
2. primary-source prior 特徵：加「URL 是否為官方頁 pattern」顯式特徵可再放大增益。
3. top-K 多樣性護欄：single-03-cncf 的 tight-K regression 是 corroboration
   獎勵多產網域——加 per-domain cap 或 MMR。
4. `enrichment/rerank.py::scoped_rerank` 已產品化未 live 測（BLOCKED on
   sidecar），是 rank 之後下一級。

**4c. 實體/關係整合**
- entity_resolution 重定位：現在的 null 是結構性的（實體=URL hash）。兩條路：
  (a) 移到 admission 之前對 raw pool 做，讓合併重複強化 corroboration 訊號；
  (b) 封存到本體論改掉（頁面→世界實體）之後再啟用。**不要在現在的位置繼續投資。**
- hyperedge 定位：不是排序/檢索的修法，是輸出表示的修法——見第 3 點接點。先只
  掛 `find_partnership_signals` objective，範圍最小、GT 天然 n-ary。前置依賴：
  頁面→實體抽取級（沒有它 hyperedge member 還是頁面 hash，沒有意義）。

**4d. 產品定位（最關鍵，不迴避）**

**明確建議：不要調 pipeline 去追「單一精確事實查找」，宣告為非目標（或降級為
委派給 agent step 的子能力），Salva 重新定義在 bare agent 做不到的持久化多實體
關係場景。**

理由：bare Haiku 3.28 次搜尋拿 0.499——單事實查找是每個 LLM agent 框架的原生
commodity 能力，Salva 要在這條軸上贏，唯一路徑是把自己改造成 react loop，那就
沒有存在理由了。Salva 已被實證的差異化資產全部在另一條軸：跨 run 複利記憶（E9
PASS）、n-ary 事實保留（hg_penetration，binary 會誤報「無控制股東」）、
jurisdiction source routing 自我優化、可稽核 evidence chain——這些是 bare
agent 結構上不做的事。

**兩個必須誠實面對的代價**：(1) 縮小 TAM，且「複雜多實體場景」目前 multihop
tier 也在輸——定位宣言必須伴隨 4a+4c 的實作，否則只是用排除法定位、沒有一個
能贏的展示；(2) 即使定位改了，retrieval 還是要修——複雜場景的檢索天花板不會
自動變高。混合形態是可行折衷：Salva 做編排+記憶+關係組裝，收斂型子任務透過
query_proposal/sidecar 委派給 agent 一步完成，保留 Salva 的殼、借 bare agent
的收斂能力。

## 5. 給 owner 的行動方案（按優先序）

1. **admission 預設切 rank + 補 precision@K**——已驗證 0 regression、一行 env
   預設的事；不做：Salva 出廠預設 recall=0.000，任何 demo 第一次跑就是零產出。
2. **query formulation 重建（實體錨定+域名鎖定閉環+接通 query_proposal）+ 加
   第二 provider**——83% 天花板在這裡，selection 已近打滿，是唯一能把
   0.122→逼近 bare agent 的槓桿；不做：Round 3 不管測什麼都會再次得到「上游
   沒料」，下游機制繼續空轉。
3. **定位拍板（owner 決策）：單事實查找宣告非目標或降為委派子能力，benchmark
   重切成 n-ary GT 的關係型任務集**——現在的 task_set_v2 量的是 Salva 結構上
   不該打的仗；不做：工程資源持續被引導去跟 commodity 能力對齊，差異化資產
   繼續閒置。
4. **n-ary 事實抽取級接進 live pipeline**（`service.py:186` 接點 →
   `persist_discovery_run(hyperedges=...)`，先限 partnerships objective）——
   把唯一已實證的差異化從 demo 變成產品面的最小路徑，持久層參數已存在、零
   schema 改動；不做：「Salva vs bare agent」永遠答不出來。
5. **實體本體論改造：頁面→世界實體**（改 `legacy_result_to_entity` 的 1:1
   錨定與 md5(url) 身份）——資料流形塌縮的源頭，也是 ER 與 hyperedge member
   有意義的前置條件；成本最高、牽動 schema 與所有 fixture，排最後，在 1-4
   驗證定位正確後再動。

## 風險與不確定處（fable 自揭）

- Arm A 只跑 1 rep（協定要 3），0.499 無變異數估計；4 倍差距量級可信、精確值
  不可信。
- rank 的 3/3 轉換是 N=3；方向一致但非統計證明。
- query 稀釋診斷（4a-1）是從代碼路徑+single-01 的 4 筆垃圾結果推斷的——
  raw_results_round2 沒記錄實際發出的 query 字串，Round 3 harness 應補上逐
  query 記錄以直接驗證。
- 所有 replay 數字建立在單 provider（ddgs）+ embedding hash-fallback 的降級
  環境上；換真實多 provider + Jina embeddings 後，crosslang 任務的絕對數字
  可能明顯不同。
