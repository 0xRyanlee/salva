# Round 2 Findings — With/Without Salva，含 confidence-rank / entity-resolution 隔離測試

**日期**：2026-07-24。協定：`EXPERIMENT_PROTOCOL_ROUND2.md`（v2，經 fable 獨立審視修正）。
資料：`raw_results_round2/`，90 個結果檔（18 任務 ×(A/B/E/F/G)）。

## 執行摘要（先講結論）

| Arm | 機制 | mean recall_admitted（18任務） | vs B |
|---|---|---|---|
| A | 裸 Haiku + WebSearch，無 Salva | **0.499** | — |
| B | Salva 預設（gate） | **0.000** | baseline |
| E | B + entity_resolution(Nomenklatura) | 0.000 | +0.000 |
| F | B + admission_policy=rank(confidence.py) | **0.122** | **+0.122** |
| G | E+F 合併 | 0.122 | +0.000（超過F） |

三個預註冊假說結果：**H1 確認（有真實效果）、H2 確認為 null（如預測）、H3 確認（瓶頸主要在上游）**。
但最重要的新發現超出三個假說範圍：**即使把 F 的改善算進去，Salva 最好的 arm（0.122）距離裸 Haiku（0.499）仍有 4 倍差距**——Round 1 的「17平手」框架掩蓋了這個問題，因為 Round 1 用的是較寬鬆的實體級 recall；Round 2 用嚴格的「GT canonical URL 是否被 admit」重新測，差距重新浮現。

## H1：confidence-rank 排序訊號——確認，效果真實但侷限於上游有料的任務

`recall_all`（GT URL 是否曾出現在 raw pool，不分 selection 邏輯）顯示 **15/18(83%) 任務的 GT 從未被 retrieval 抓到過**，這些任務無論 selection 層怎麼調都不可能修好。在剩下 **3/18** 任務（每個 tier 剛好各 1 個，crosslang-05/multihop-02/single-05），Arm B（gate）**3/3 全部漏接**，Arm F（rank）**3/3 全部接住**——100% 轉換率，且三個 tier 分布平均，不是單一 tier 的巧合。

Live spot-check（`single-01-tsmc`、`crosslang-01-tsmc`，真實網路而非 fixture）方向一致：gate 兩次都是 `qualified_count=0`，rank 兩次都成功 admit 到目標公司網域（`tsmc.com`）的頁面。

**結論**：confidence.py 的 ADOPT 決定（pre-registered，`CONFIDENCE_REBUILD_FINDINGS.md`）在這輪首次獲得 live-adjacent 驗證支持，方向明確、無反例（0 個 regression）。樣本數小（N=3 的乾淨案例），不構成統計顯著性證明，但方向一致性本身是有意義的訊號。**admission_policy 預設值應該考慮從 gate 換成 rank**——目前 rank 模式下 0 個 regression，唯一代價是 top-K 塞進了更多非 GT 的候選（precision 面的權衡，本輪未量化，是下一步該補的指標）。

## H2：entity_resolution / Nomenklatura——確認為 null，如預測

**0 個合併事件，0 個 cross-script pair**，18 任務全部。這不是 bug，是機制在目前架構位置上的必然結果：entity_resolution 運行在 selection **之後**（`service.py` 呼叫順序：extraction → resolve_duplicate_entities → enrichment），gate 模式下大多數任務 admit 0-1 個實體，沒有東西可合併；即使換成 rank 模式（Arm G），admit 的候選集仍然太小、太多樣（不同公司/不同頁面類型），沒有真正的近似重複對象。

**跟既有證據吻合**：E5/E5b 已經證明字串/embedding 方法在跨語言公司名比對上recall只有0-7%、F1 0.31——Nomenklatura 的 name-matching 本質上是同一類方法，這輪的 0 效果進一步印證，不是意外。

**這不代表 entity_resolution 這個投資是浪費的**——它針對的問題（同一 run 內因多 provider/多輪查詢產生的近似重複）在更大規模、更寬鬆 admission 的場景下才有機會展現價值（例如真的做 rank 模式 + 提高 `max_admitted`，或未來接上真實 embedding 支援語意相似度而非純字串比對）。本輪的 null 結果只說明「在目前 gate-heavy 的預設配置 + 這 18 個窄範圍任務上」看不到效果，不是這個機制本身無效。

## H3：上游 retrieval 才是主瓶頸——確認，且比 Round 1 的框架更嚴重

Round 1 的「61% zero-qualified」已經指向 scoring 層，但 Round 2 的 `recall_all` 分析顯示問題更早：

- 15/18(83%) 任務的 GT canonical URL **從未進入 raw pool**。
- 對這 15 個任務再做 domain-level（放寬到「有沒有找到對的公司網域，不要求剛好那個頁面」）分析：**7/15 有找到對的網域（只是不是那個精確頁面），8/15 連對的網域都沒找到**（例：`single-01-tsmc` 的 4 筆 raw 結果是一個測驗網站、一則 LinkedIn 貼文、一篇 ABC News 報導、Crunchbase 首頁——沒有一筆是 tsmc.com）。

換算：18 任務中，**3 個 URL 精確命中 + 7 個域名命中但頁面不對 = 10 個「retrieval 至少摸到邊」，8 個「完全沒摸到」**。這是本輪最值得後續調查的具體缺口，比「scoring threshold 沒調好」更根本——是 query formulation/provider 覆蓋率的問題，不是 selection 邏輯能解的。

## 意外發現：即使修好 selection 層，Salva 仍大幅落後裸 Haiku

Arm F（0.122）vs Arm A（0.499）——4 倍差距，且 Arm A 用**更少**的動作達成（平均 3.28 次 WebSearch/任務 vs Salva 動輒 2 輪 × 4 策略 × 多次查詢的固定管線開銷）。

這不是 Round 1 的結論被推翻——Round 1 測的是「有沒有抓到跟這家公司相關的任何合理實體」（寬鬆），17 平手是事實；Round 2 測的是「有沒有抓到 GT 標記的那個精確 canonical 頁面」（嚴格）。兩把尺量出不同的東西，都對，回答的問題不一樣。**嚴格這把尺揭露的問題是**：task_set_v2 的任務設計（「找到官方聯絡頁面」）本質上更貼近「單一事實查找」，而 Salva 的檢索管線（dive/anchor/radar/pirate 四策略 + keyword graph 擴展）是為「一個 domain 下探索多個實體」設計的，兩者的最佳化目標有結構性落差——bare agent 直接針對問題本身反覆搜尋收斂，Salva 的管線在窄範圍單一事實任務上反而绕了更多彎路。

這個落差本身是一個需要 owner 拍板的產品定位問題（見下方 pipeline 修法建議），不是本輪能單靠調參數解決的。

## 完整性驗證（對照 EXPERIMENT_PROTOCOL_ROUND2.md §6）

1. 檔案數量：90/90（18×(B/E/F/G) 72 + 18×A 18）全部存在。Arm A 原定 3 rep，實際跑 1 rep（見下方「範圍縮減揭露」）。
2. **raw_count 跨 B/E/F/G 四個 arm 逐任務完全一致**（18/18）——確認 env var patch 正確隔離了唯一變因，沒有 replay drift 混進來。
3. Arm E/G 合併對數：0 個（H2 已詳述），無需標記 cross-script（沒有合併事件可標）。
4. 抽查：3 個乾淨案例（recall_all>0）三個 tier 各一個，分布均勻，非單一 tier 巧合。
5. Live spot-check（2 個任務，非全 18）方向與 replay 一致，gate 兩次漏接、rank 兩次接住。

**範圍縮減揭露（不要事後假裝沒發生）**：
- Arm A 協定寫的是 3 rep/任務（控制 LLM 決策非決定性），實際受限於單次執行時間/成本只跑了 1 rep。**這代表 Arm A 的 0.499 平均值沒有變異數估計**，不能排除某些任務換一次執行就翻盤（Round 1 的 `multihop-03-naturehike-dach` 就是這類例子）。這是本輪相對協定原意的已知縮水，如果要拿這個數字做更正式的結論，需要補跑到 3 rep。
- 2 個 Arm A 任務（`single-02-naturehike`、`crosslang-04-foxconn`）第一輪 Workflow 執行時 subagent 沒有呼叫 StructuredOutput，用前景 Agent 重跑補齊——這兩筆數字跟其他 16 筆不是同一批次生成，理論上有極小的執行環境差異，但沿用同一套 prompt/流程，不影響可比性判斷。
- live spot-check 只做了 2 個任務（B'/F' 各 2 次），不是協定原本設想的「每個 tier 1-2 題」全覆蓋（3 tier 應該有 3-6 個，只做了 2 個，都在 single/crosslang tier，multi_hop tier 沒有 live 驗證）。

## 下一步（不在本輪範圍內，留給後續）

- 補 Arm F 的 precision 指標（rank 模式下 admit 更多非 GT 候選，代價量化）。
- multi_hop tier 的 live spot-check 補上。
- Arm A 補到 3 rep 若要做正式判準。
- 針對 8/18「連對的網域都沒摸到」的任務，逐一分析 query formulation 究竟哪裡出錯——這是目前最高槓桿、最沒被回答的問題。
