# Arm A/B Round 2 — With/Without Salva，測試本 session 新落地的三個機制

**修訂記錄**：v1 草案經 fable 獨立審視後全面修正（v2，本檔案）。v1 的三個
致命缺陷與修法：
1. H1/H3 用 `qualified_count>0` 當判準——但 `admission_policy="rank"`
   無條件 admit top-25（`core/controller.py:260-266`），Round 1 已證
   raw pool 18/18 非空，所以這個判準機械上必然成立，跟排序品質無關。
   **改用「GT entity 是否出現在 admitted top-K」**。
2. H2 預測方向跟既有證據（E5/E5b：字串/embedding 方法跨腳本 recall
   0–7%、F1 0.31 FAIL）相反，且有選擇效應陷阱（entity_resolution 只在
   gate 模式已產出實體的任務上跑，Round 1 的 7 個有產出任務裡 5 個剛好
   是 crosslang，會被誤讀成「Nomenklatura 對跨語言有效」）。**反轉預期
   為「預期 0 個 cross-script merge」，並要求記錄逐對合併結果標記
   cross-script**。
3. 全 live、無 drift noise floor、無 raw pool 記錄，四個 arm 間的差異
   無法歸因是機制效果還是網路結果漂移。**改用既有 frozen-corpus fixture
   harness（`experiments/salva_v2/harness/`）做 B/E/F/G 主要比較（byte-
   identical raw pool，零網路雜訊），live 呼叫只留給一個小規模 spot-check
   驗證 replay 與現實方向一致**。

## 0. 承接關係

Round 1（`e465af4`→`ebcea7b`→`2f92989`）：18 任務 17 平手/1 勝(非
Salva貢獻)/0敗，瓶頸在 scoring 層——61% 的 Arm B run 產出 0 個 entity
即使 `retrieval_health: ok` 18/18 成立。後續 scorer threshold 修正
（`RESCORE_COMPARISON.md`）沒能翻盤，揭露「更深層的 vocabulary/
trusted-source calibration gap」。

Round 2 測試 Round 1 之後新落地、直接對應這個瓶頸的兩個機制：
- **confidence.py 排序**（已 pre-registered ADOPT，`CONFIDENCE_REBUILD_
  FINDINGS.md`）——本輪首次在 `admission_policy=rank` 下測試它對
  **哪些 entity 被 admit** 的實際影響（不是「有沒有 entity 被 admit」）。
- **entity_resolution.py（Nomenklatura）**——對應 `hg_penetration/
  README.md` checklist 未打勾的「Cross-source entity resolution」項。

rerank.py（LLM rerank）本輪**不測**——需要真實 sidecar LLM，CC 無法在
sandbox 安全自測，明確標記 BLOCKED。

## 1. 預註冊假說

- **H1**：Arm F（`SALVA_ADMISSION_POLICY=rank`）相對 Arm B（gate）——在
  admitted top-K（K = `len(ground_truth_entities)`，逐任務讀 task_set_v2
  各任務的 GT 數量，不用固定常數）裡，**GT entity 出現的任務數**有可觀測
  提升。判準：≥3 個任務從「GT 不在 top-K」轉為「GT 在 top-K」。
  （**不用** `qualified_count`，因為 rank 模式下這個數字對 admission
  品質無資訊量。）
- **H2**（反轉自 v1）：entity_resolution 合併結果中，**預期 0 個
  cross-script pair**（依 E5/E5b 既有證據，Nomenklatura 的 name-matching
  本質上是同一類方法）。若合併確實發生，預期集中在同腳本的近似重複
  （如 "TSMC" vs "TSMC Ltd" 這類，不是 "台積電" vs "TSMC"）。
  對 recall@gt 的預期效果是 **0**（合併只會減少實體數，不會讓 GT
  突然出現在池子裡）；唯一可能的效果是 precision/去重計數面。
- **H3**（否證條件，改用 recall@all 而非 qualified_count）：若 raw pool
  裡 GT entity 本來就不存在（`recall@all=0`），則任何 selection 層機制
  （排序或合併）都不可能救回來——這種任務要從 H1/H2 的判定裡剔除，歸類
  為「上游 retrieval 缺口」，不是「selection 層沒生效」。

## 2. Arms 與執行方式

| Arm | 設定 | 執行方式 | 覆蓋範圍 |
|---|---|---|---|
| A（bare） | Haiku + WebSearch，無 Salva | 並發 Haiku agent（Workflow），3 rep/任務 | 全 18 任務，live |
| B（baseline，replay） | `SALVA_ADMISSION_POLICY=gate`（預設） | frozen-corpus replay（`harness/replay_retriever.py`） | 全 18 任務，offline |
| E（entity-resolution，replay） | B + `SALVA_ENABLE_ENTITY_RESOLUTION=true` | 同上 | 全 18 任務，offline |
| F（rank，replay） | B + `SALVA_ADMISSION_POLICY=rank` | 同上 | 全 18 任務，offline |
| G（combined，replay） | B + 兩者都開 | 同上 | 全 18 任務，offline |
| B'/F'（live spot-check） | 同 B/F，但走真實網路 | 直接 CLI 呼叫 | 精簡子集（每 tier 挑 1-2 題），驗證 replay 結論方向與現實一致，不是獨立假說判定來源 |

B/E/F/G 用 replay 是本輪相對 v1 最大的方法論修正：`SalvaController` 建構
時機在 `salva_core/service.py::execute_discovery` 內，retrieval 層被
`ReplayRetriever` 凍結後，B/E/F/G 四個 arm 的 raw pool 是**同一份錄製好
的 fixture**，唯一差異變因就是 env var 控制的 selection 邏輯本身——徹底
消除 v1 被抓到的 drift 混淆問題。

Arm A 沒有辦法用 replay（bare agent 不呼叫 Salva 的 retriever，凍結
Salva 的 fixture 對它沒有意義），維持 live，3 rep 理由不變（LLM 決策
非決定性）。**Arm A 的分析角色**（回應 fable 審視第 5 點）：不是 H1/H2/
H3 的比較對象——H1-H3 全部是 B/E/F/G 內部比較。Arm A 提供的是 Round 1
已建立的「business-outcome 天花板參照」，本輪只需確認這個天花板沒有
劇烈偏移（例如網路環境退化導致 Arm A 這次也大幅失手），不需要重新論證
Salva vs bare 的勝負（Round 1 資料已經是乾淨事實）。

## 3. Replay 執行細節

用 `experiments/salva_v2/harness/` 既有機制：`no_network_guard()` +
`patch("salva_core.service.RoutedRetriever", replay_factory)`，額外在
呼叫 `execute_discovery` 前設定對應 env var 組合。用
`patch("salva_core.service.SalvaController", controller_factory)`
（沿用 `test_query_proposal_harness_replay.py` 的既有 pattern）捕獲
controller instance，跑完後讀 `controller._all_results`（`UnifiedResult`
list，含每筆 `source_url`）算 **recall@all**（GT 的 source_url 是否
出現在任一 raw result 裡，不分 host/query 差異只比對 URL 正規化後是否
相符），跟 `controller.run()` 回傳的 selected/admitted 對照算
**recall@admitted**。

## 4. 評分指標

- `recall_all`（GT source_url 是否出現在 raw pool，逐 task 逐 GT-entity 二元）
- `recall_admitted`（GT source_url 是否出現在該 arm 最終 admit 的 entity 集合）
- `entities_merged_count`、merged pairs 明細（僅 Arm E/G，逐對標記
  same-script/cross-script）
- `raw_count`（各 arm 的 raw pool 大小——replay 下四個 arm 應該完全相同，
  若不同代表 patch 沒生效或 env var 讀取有誤，是完整性檢查訊號本身）
- Arm A/B'：沿用 Round 1 的 precision/recall/f1/requests_used/
  `business_outcome_judgment`（質性判斷，回補 v1 遺漏的 Round 1 指標）

## 5. 實體比對規則（跑前寫死，不能事後調整）

GT 比對只用 `source_url`（task_set_v2 的正規化欄位）做**規範化後精確
比對**：去除 URL 尾端斜線、統一小寫 host、忽略 query string；不做
domain-only 比對（Round 1 分析中途被迫從 domain match 改成 entity-name
match，本輪直接用更精確的 source_url 比對避免重蹈覆轍，但明訂規則不是
「同 domain 就算」，必須是同一個標準化後的 URL 路徑）。

## 6. 完整性驗證清單

1. 檔案數量：18 任務 ×(B/E/F/G 四個 replay + A 三次 rep) = 126，另加
   live spot-check 子集。逐一確認結果檔案存在。
2. **四個 replay arm 的 `raw_count` 必須逐任務完全相同**——不同就是
   patch/env var 沒生效，不是機制差異，要先修好才能信任其他指標。
3. Arm E/G 的 merged pairs 明細逐對人工標記 cross-script/same-script，
   驗證 H2 的預測方向。
4. 抽查 3 個 Round 1 記錄為 `qualified_count=0` 的任務，在 Round 2 的
   B（replay）下重算 `raw_count`/`recall_all`，確認跟 Round 1 live 數字
   量級一致（fixture 是 Round 1 之後才錄製的，理論上會有出入，這裡只
   檢查沒有離譜到代表 fixture 錄製本身有問題）。
5. Live spot-check（B'/F'）跟對應任務的 replay（B/F）結果方向一致
   （不要求數字相同，只要求「GT 有沒有進 admitted」這個布林結論相符）
   ——不一致就要交代原因（多半是 live 當下的 provider 結果跟錄製時不同）。

## 7. 非目標聲明

不是正式統計顯著性檢定；不重新論證 provider 選型；rerank/query-proposal
本輪不測（BLOCKED，需 owner 的真實 sidecar）；不重新驗證 Round 1 的
bare-vs-old-Salva 結論（已是乾淨事實，Arm A 本輪只是天花板參照）。
