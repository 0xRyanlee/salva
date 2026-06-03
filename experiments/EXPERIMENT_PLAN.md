# Salva 實驗計畫 — 為開發奠定理論基礎

> 原則:在做開發工作前,用一系列小實驗把核心主張**逐一證明或證偽**,讓開發站在證據上而非希望上。
> 每個實驗圍繞 ≥1 個**關鍵驗證點(VP)**,**過程(腳本+資料)與結果(findings+輸出)都存檔進 git**。
> 全部驗證完 → 取得理論基礎 → 進入開發階段。

## 關鍵驗證點(要建立的理論)

| VP | 主張 | 狀態 |
|---|---|---|
| VP1 | n-ary 超圖保留二元分解會丟的關係事實(表示忠實度) | ✅ E1 |
| VP2 | 公開源能提供股權事實(分法域可得性) | ✅ E2(US 證;CN/TW 上市待真拉) |
| VP3 | 雜亂真實 filing → 結構化 n-ary 事實(端到端獲取) | ✅ E3(SEC) |
| VP4 | 路由表從 source_attempts 自我優化(authority ≠ reachability) | ✅ E4(in-memory;持久化待 E9) |
| **VP5** | **跨語言實體解析**:同一主體在 中/英/拼音/ticker/簡稱 下能合併成一個 canonical entity | ⬜ E5 |
| **VP6** | **跨語義關係/事實合併**:等義關係與角色(控股/ownership/持股;董事長/chairman)正規化;多源同一事實合併為一條超邊+多證據 | ⬜ E6 |
| VP7 | 超圖上的語義檢索 + 二跳:embedding 預篩 + 結構擴展,勝過關鍵詞 | ⬜ E7 |
| VP8 | 投影/互通:canonical 超圖 → HIF round-trip;bipartite/star 投影視覺窗(非黑箱) | ⬜ E8 |
| VP9 | 持久化複利:跨多 run 在同領域上 yield/精度可量測上升(誠實版複利) | ⬜ E9 |

## 存檔約定

每個實驗 `Ek`:
- 可重現腳本 `experiments/.../ek_*.py`(**過程**)
- `Ek_FINDINGS.md`:假設 / 方法 / 結果 / **誠實裁決**(**結果**)
- 本 `EXPERIMENT_PLAN.md` 維護狀態 + 一句裁決(索引)
- 真實資料實驗附 evidence(URL/來源),合規優先(只用合法公開源)

---

## 已完成(E1–E4)

- **E1 表示** (VP1) — `hg_penetration/run.py`。裁決:✅ n-ary 在「協同控制/多角色事件」勝;分層有效持股不是差異化(誠實)。
- **E2 可得性探針** (VP2) — `hg_penetration/probe_sec.py` + `PROBE_FINDINGS.md`。裁決:✅ 死穴非一致;上市公司 US/UK/TW/CN 可得;摩擦在私人公司 + 實體解析。
- **E3 真實端到端** (VP3) — `hg_penetration/run_real.py` Part 1。裁決:✅ 真拉 Chatham Lodging Trust 15 實體 §13(d)(3) 集團 → 一條 n-ary 超邊 + 證據。
- **E4 路由自我優化** (VP4) — `hg_penetration/routing.py` + run_real Part 2。裁決:✅ CN gsxt 真實失敗→降級翻轉;US SEC 命中→boost。

---

## 待執行(E5–E9)

### E5 — 跨語言實體解析(VP5)〔最高優先,user 指定〕
- **假設**:同一主體跨 中/英/拼音/ticker/別名 可被解析為一個 canonical entity,且 normalized+embedding 法顯著優於 naive 字串比對。
- **方法**:建跨語言別名資料集(例:台積電 / TSMC / Taiwan Semiconductor Manufacturing / 台湾积体电路 / TSM / 2330)。比較 (a) exact、(b) normalized(轉拼音/繁簡/去後綴 Ltd/股份有限公司)、(c) embedding 相似(Jina multilingual)、(d) 借 OpenSanctions Yente/Nomenklatura 思路。真實樣本:CN registry 名 vs SEC 名 vs 新聞名。
- **存檔**:各法的 recall/precision + 何種組合最穩。
- **裁決標準**:跨語言對能否在可接受精度下合併;哪一層(規則 vs embedding)貢獻最大。

### E6 — 跨語義關係/事實合併(VP6)〔user 指定〕
- **假設**:等義關係/角色跨語言可正規化到一套 schema;多源同一事實能合併為一條超邊 + 多 evidence(provenance 不丟)。
- **方法**:關係/角色對映表(控股=持股=ownership;董事長=chairman=Chair;董事=director)→ FtM 對齊。測「控股 70%」「owns 70%」「持股 70%」三源 → 合併成一條 Ownership 超邊,保留三條 evidence。衝突處理(不同來源不同 %)。
- **存檔**:對映表 + 合併前後 + 衝突案例。
- **裁決標準**:多源多語言能否收斂成一致 schema 而不丟 provenance、不誤併。

### E7 — 超圖語義檢索 + 二跳(VP7)
- **假設**:node/hyperedge 文本 embedding 預篩 + 二跳遍歷,回傳相關子圖優於關鍵詞。
- **方法**:小超圖,Jina embed 節點;查詢「歐洲做 distributor 的關聯主體」→ 向量 top-k → 二跳擴展;對照純關鍵詞。
- **存檔**:檢索品質對照。
- **裁決標準**:語義+結構是否優於關鍵詞 baseline。

### E8 — 投影 + HIF 互通 + 視覺窗(VP8)
- **假設**:canonical incidence 超圖 → HIF export 可 round-trip;bipartite/star 投影可渲染(非黑箱)。
- **方法**:export HIF → re-import → diff(無損);產 bipartite/star 投影(cy.js 或靜態圖)。
- **存檔**:HIF 樣本 + round-trip diff + 投影截圖。
- **裁決標準**:無損互通 + 可觀察。

### E9 — 持久化複利(VP9)〔誠實版,取代空殼複利〕
- **假設**:持久化 source_attempts + extraction 記憶,跨 N run 在同領域 yield/精度可量測上升。
- **方法**:同領域連跑 N 次,持久化路由記憶;量 recall@budget / queries-to-yield 曲線(沿用 `benchmark/` 精神)。
- **存檔**:曲線 + 每 run 指標。
- **裁決標準**:曲線是否單調上升(真複利)或平(證偽 → 重估)。

---

## 順序與依賴

```
E5 (跨語言實體) ─┐
                 ├─→ E6 (跨語義關係)  ─→ E7 (語義檢索/二跳)
E3/E4 (已) ──────┘                      └─→ E9 (持久化複利)
E8 (投影/HIF/視覺) 可並行(獨立)
```

建議序:**E5 → E6 → E8(視覺,讓前面可觀察)→ E7 → E9**。E5/E6 是公司情報 beachhead 的硬核(跨語言/多源),先攻。

## 終態

E5–E9 全綠(或誠實證偽)後,Salva 的核心主張(n-ary 表示、跨語言/語義合併、語義檢索、自我優化複利、可觀察互通)都有實證基礎 → 才進入正式開發(把 `Hold` 升級成 typed-n-ary incidence store、接 Jina、做投影層等)。
