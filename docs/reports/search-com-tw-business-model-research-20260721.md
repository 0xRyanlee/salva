# search.com.tw 商業模式研究（2026-07-21）

任務：mindset 板 `salva-search-com-tw-business-model-research`。範圍：對標 Jina AI 計費模式、調研 Polar 能力邊界（取代舊 Paddle 假設）、釐清開放公開檢索對先前合規裁決的影響、判斷 landing archetype。不涉及實際代碼或收款串接。

## 1. Jina AI 定價模式調研摘要

Jina 自 2025-05-06 起把 Embeddings / Reranker / Reader 三個 Search Foundation API **統一計費結構**：全部按 **token 計費**，jina-embeddings-v3 為 **$0.02 / 1M tokens**，reranker 與其對齊，reader 同價。新 API key 內建免費額度（來源標示 100 萬～1000 萬 tokens 不等，需以官網當下數字為準），**同一 key、同一 token 池跨服務共用**（embed/rerank/read/classify 都扣同一份額度），不是分產品各自計費。用量模型是 **top-up 預付**（Stripe 付款買 token，不是月費訂閱），另疊加三檔 **rate limit 分級**（Free 100RPM/100K TPM、Paid 500RPM/2M TPM、Premium 5000RPM/50M TPM），限制的是速率不是額度本身。這對 search.com.tw 的參考價值：**單一計費單位（token 或「查詢次數」）跨所有 API 端點共用**，比起分產品定價更適合 Salva 這種多輪檢索管線（一次 discover 內部可能觸發多個 provider + LLM enrichment，難以在使用者側拆分計費顆粒度）。

## 2. Polar 能力邊界調研摘要（取代 Paddle 假設）

**確認可行**：Product/Price API、Checkout（session-based，依 IP 地理定位自動配對已啟用的幣別）、Webhook（訂閱/訂單/checkout 生命週期事件，含簽章驗證）、客戶自助 portal（訂閱管理）。**Usage-based/metered billing 已於 2025 年上線且非實驗性**（issue #5114 為設計文件，已 close 並實作）：机制是 ingest 事件 → 綁定 Meter → Metered Price 掛在 Product 上（按 unit 計價，可設 cap 上限）。**Credits/預付 top-up 模式亦支援**，且可設「無訂閱、純額度」——用盡時 Polar 不主動擋用量，由呼叫端 app 自行決定行為（這點對 search.com.tw 的免費額度用盡→轉付費流程很關鍵，行為邏輯要自己接）。**多幣別**：2025-11 PR #9339 後，單一 Product 可設定多組幣別價格，checkout 依買家 IP 自動選幣（issue #7945/#7946 均已 close）。

**不確定/需進一步驗證**：① Volume pricing（分段遞減單價，Jina 式「量大單價降」）官方標註 **coming soon，尚未上線**，目前只有線性 unit pricing，若要做階梯定價需 workaround（多 meter 疊加或人工分段）。② Polar **不支援 Paddle 式「一個 base price 自動換算各國定價」**，也不支援 Dodo 式 adaptive currency，每個幣別要手動設價——這比 Paddle 的 `unit_price_overrides` 更費工。③ 2026 新收費結構為 Starter（免費方案，5%+50¢/筆）到 Scale（$400/月，3.4%+30¢），未在公開頁面標明 usage billing / 多幣別是否分 tier 鎖定，看起來核心功能全 tier 開放，但**需要實測驗證，不能只信行銷頁**。④ **TWD 與台灣本地支付方式（超商代碼、行動支付）是否在 Polar 支援清單內，本次調研未能確認**，是落地前的硬性阻塞點。

## 3. 合規/風險邊界建議

歷史脈絡：team 先前已裁決「開放網路任意檢索」屬紅海且成熟、「OSINT 深背調」屬灰色地帶，兩者皆不納入核心，Salva 收斂到「商業實體情報」這個乾淨 beachhead。**開放一個任何人可調用的公開 web SaaS 做「任意檢索」，本質上是重新打開那扇門**——底層技術（domain-agnostic 檢索管線）對「查公司」和「起底一個人」沒有技術差異，差異只能靠治理層做。可控化做法：

1. **ToS 明列禁止用途**：人肉搜索、跟蹤騷擾、個資聚合類查詢明文禁止，而非只寫「合法用途」空話。
2. **註冊即宣告 domain_hints**（沿用既有 `DomainVocab` 架構）：偏離商業情報方向的查詢模式（自然人姓名+住址+電話跨維度交叉）觸發降級或人工審查，技術上不難做，因為 Salva 本就有 `intent.domain_hints` 欄位。
3. **免費層限定低風險 domain**（companies / market_intel），深度交叉查詢只開放給已驗證（KYC 級別視需求）付費帳戶，並保留 `run_id`/`job_id` 稽核鏈——這正好是 Salva 既有的可觀測性設計，不需新建。
4. 誠實面對局限：**ToS 對惡意使用者的實際嚇阻力有限**，真正的防線是 rate limit + 查詢模式異常偵測 + 帳戶分級，不是文字本身。

## 4. Archetype 分類判斷

依 `/Volumes/Astoria/Projects/CLAUDE.md` 的兩種原型：**search.com.tw 公開 web 端應走「Open tool / ecosystem hook」**——CTA=使用/探索，SEO/AEO 優先，免費額度是流量入口，這正是 CLAUDE.md 原文舉例的「multi-user search」類型。但因為背後有實際計費（不是純廣告變現），實務上是**混合模式**：免費層做導流（Jina 式）+ 額度用盡後 upsell 到付費層（Polar metered/credits 接的正是這段），不是純粹的「流量→廣告」ecosystem hook。**App 端訂閱/BYOK 應走「Paid product」原型**——CTA=下載/訂閱，需要 pricing、比較、信任內容，因為使用者要投入自己的訂閱額度+API key 做客製工作流，是高涉入付費決策，比照 Mindset/Sparkie/Cuckoo 既有模板即可。兩者共用底層元件，但落地頁的敘事與轉換路徑必須分開設計。

## 5. 開放性問題清單（需 owner 拍板）

1. Polar 是否支援 TWD 與台灣本地支付方式——本次調研未能確認，是 search.com.tw 主打台灣市場前的硬性阻塞點，需直接查 Polar 官方幣別清單或聯繫其 support 確認。
2. Volume pricing（階梯式單價遞減）Polar 尚未原生支援，若要做 Jina 式「量大更便宜」，需自建 workaround（多 meter 分段），值不值得做需要先定出目標定價曲線。
3. 免費層的具體額度數字（多少次查詢/多少 token）與 ToS 禁止用途的具體法律措辭，本研究只給方向性建議，未給可直接落地的數字或文字。
4. **最關鍵的一個**：公開 API 要不要做 KYC/實名制門檻來區分「商業情報」與「人肉搜索」用途？不做，ToS 文字約束的嚇阻力有限；做，會拉高進入門檻、可能扼殺 Jina 式輕量開放帶來的流量效果。這是技術與調研都無法代為拍板的核心取捨，直接決定 search.com.tw 從第一天要走「開放但淺」還是「有門檻但深」。
