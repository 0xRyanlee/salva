# 可自訂黑箱檢索引擎 — 架構研究與提案 (2026-07-21)

## 背景
Owner 方向：把 Salva「injectable, not hardcoded」的內部設計哲學，從「呼叫方在 Python 層構造物件」升級為「使用者透過 API/設定檔可見可控」。本文盤點現況、調研外部參考架構、提出初步提案。

## 一、現有可插拔點盤點（按離「使用者可控」的距離排序）

| 檔案/Class | 現況 | 距離使用者可控 |
|---|---|---|
| `salva_core/schemas/request.py` `DomainHints`（經 `service._resolve_vocab`） | **已經是 API 級可控**：`DiscoveryRequest.intent.domain_hints` 讓呼叫方在單次請求裡疊加 synonym/region/signal/source_hints/noise_terms，merge 進 `core/domain_vocab.py` registry 的 base vocab。 | 已完成，零工作量 |
| `TransformOptions`（`salva_core/transforms.py` + `request.py`） | **已是 API 級**：`fields`/`rename`/`drop_nulls` 讓呼叫方在既有 `output_profile` 產出的欄位上做子集/改名，不需碰代碼。但**新增一種全新 profile 形狀**（如 legal-tech 專用欄位）仍需改 `_apply_profile()` 的 if/elif 分支。 | 極近（reshape 已可控；new-shape 仍要改碼） |
| `processing/scorer.py` `ScorerConfig`（經 `service._build_scorer`） | **部分曝光**：`qualify_threshold` 是 top-level API 欄位可直接覆蓋；`domain_hints.signal_terms/noise_terms` 會被塞進 `high_signals`/`negative_signals`。但六個權重（w_content...w_recency）、`noise_domains`/`trusted_sources` **刻意不開放**（`_build_scorer` 註解明講：不讓呼叫方自報 source trust）。 | 中；權重是設計上被鎖住的邊界，不是遺漏 |
| `core/keyword_graph.py` / `Intent.max_rounds` | max_rounds 只能透過 `intent.constraints={"max_rounds": N}` 這個型別鬆散的 escape hatch 設，無 schema 驗證、無文件化為正式欄位。 | 中低；有通路但非一等公民 |
| `salva_core/vector_backends.py` `resolve_semantic_vector_backend()` | **process 級單例**，靠 `SALVA_SEMANTIC_VECTOR_BACKEND` 環境變數選 `jina_omlx`/`sqlite_vec`/`hybrid_hash`/`scalar_hash`，用全域 `_instance_lock` cache instance。同一進程內所有請求共用同一 backend，無法逐請求切換。 | 遠；要做到per-request需拆全域單例模式 |
| `core/controller.py` 的 `admission_policy`/`ranking_weights`/`enable_query_proposal` | **目前完全未連到 API**：`salva_core/service.py::execute_discovery()` 構造 `SalvaController` 時根本沒傳這三個參數，永遠吃 default（`"gate"`/`None`/`False`）。這是三者中距離最遠的——不只沒開放給使用者，連 service 層都還沒接上。 | 最遠；先補 service 層 wiring 才談得上開放 |
| `salva_core/relation_ontology.py` `_RELATION_MAP` | 純內部 dict，無任何 request 欄位、無 registry 函式（對比 `domain_vocab.py` 有 `register_domain()`）。要擴充 relation 類型只能改源碼。 | 最遠；連 runtime 擴充機制都沒有 |

**關鍵發現**：Salva 現有的「injectable」設計哲學已經在 DomainVocab 和 TransformOptions 兩處走到 API 級，證明「參數化 JSON 配置」這條路本來就是專案既定路線，不是新方向——owner 的方向本質上是**把這個模式補齊到 scorer 權重、vector backend、controller 三個參數，並讓 relation ontology 有 runtime registry**，而非發明新機制。

## 二、外部參考架構調研

1. **Haystack (deepset) YAML pipeline** — pipeline 是 typed-input/output 的 DAG，元件（retriever/reranker/preprocessor）靠實作標準介面（`run()`）即可熱插拔，整個 pipeline 可序列化成 YAML 版控、部署時免改碼替換元件。取捨：表達力強但學習曲線高，本質上是「declarative code」而非純參數表。
2. **txtai workflow** — `embeddings` 與 `workflow`（tasks 陣列，每個 task 一個 `action`）都用 YAML 頂層 key 定義，action 可以是內建（index/upsert/search）或指到自訂 callable。取捨：YAML 直接映射 Python callable，換 embedding model 只需改 path 字串，換邏輯仍要寫 Python 並註冊。
3. **LangChain/LangGraph `configurable_fields` + `config_schema`** — Runnable 用 `RunnableConfigurableFields` 把「哪些欄位可在 runtime 被覆蓋」顯式聲明，LangGraph 的 `StateGraph(config_schema=...)` 讓 model/vectorstore/tool 選擇下放到單次呼叫的 config dict。取捨：這是最貼近「single API call 帶 config override」模式的先例，且**明確區分「宣告哪些欄位可配置」與「開放任意程式碼」**——這正是安全邊界設計的核心參考。
4. **Elasticsearch/OpenSearch plugin 系統（對照案例）** —安裝級擴充：JVM plugin 由 admin 在部署時裝進節點、需重啟，不是逐請求可調的東西。這說明「code-level 擴充」在成熟系統裡通常被推到**部署/管理員層**，而非終端使用者的 per-call 參數，是重要的安全邊界參照。

## 三、初步架構提案

**介面形狀**：仿 LangChain configurable_fields 模式，在 `DiscoveryRequest` 新增一個**參數化（非程式碼）**的 `engine_overrides` 欄位，而非新端點——理由是 Salva 的核心單位本來就是一次 `/v1/discover` 呼叫（stateless、event-triggered），配置應隨請求走，不需要獨立的持久化 `/v1/engine-config` 資源。草案 shape：
```json
"engine_overrides": {
  "scorer_weights": {"w_content": 0.3, "w_signal": 0.25, ...},
  "vector_backend": "jina_omlx",
  "max_rounds": 5,
  "admission_policy": "rank",
  "enable_query_proposal": true,
  "relation_hints": {"custom_type": ["surface form 1", "surface form 2"]}
}
```
新增一個 `Pydantic` model（`EngineOverrides`），每個欄位都有明確型別與邊界（`ge`/`le`），而不是自由 dict——延續 `DomainHints`/`TransformOptions` 已驗證過的模式。

**安全邊界（明確結論）**：**只做參數化配置，不做程式碼級 plugin（不接受使用者上傳 Python 函式/表達式）**。理由：(a) Salva 是多租戶 self-hosted runtime，任意 code execution = RCE 攻擊面，且 `enrichment/` 已有明確邊界「bounded prompts only, no free-form LLM calls」，開程式碼 plugin 直接違反 CLAUDE.md 既定護欄；(b) `scorer.py::_build_scorer` 已經示範了這個邊界該怎麼畫——「聲明可調的是什麼（signal_terms/noise_terms/qualify_threshold），刻意不讓呼叫方自報 source trust」，`engine_overrides` 應延續同一分寸，不開放 `noise_domains`/`trusted_sources`。

**Quick win（低風險，可先做，不需 owner 拍板）**：
1. 把 `admission_policy`/`ranking_weights`/`enable_query_proposal` 從 `execute_discovery()` 補接到 `SalvaController` 構造——目前連 service 層都沒連，這是純粹的遺漏，不是設計問題。
2. `relation_ontology.py` 補一個 `register_relation()` runtime registry 函式，鏡射 `domain_vocab.py::register_domain()` 已有的模式。
3. `max_rounds` 從 `constraints` 鬆散欄位升格為 `DiscoveryIntent` 的正式型別化欄位（`ge=1, le=10` 之類邊界）。

**需 owner 拍板的大方向**：
1. `scorer_weights` 開放粒度——全六權重都給改，還是隻給幾個安全的（如 w_content/w_recency），把 w_signal/w_source 這類容易被濫用來繞過 noise gate 的鎖住？
2. `vector_backend` per-request 切換要不要做——目前是 process 級單例，改成 per-request 需要拆 `resolve_semantic_vector_backend()` 的全域 cache 模式，是有實質工程成本的重構，不是加欄位而已。
3. 超圖化/圖化模式是否要做成 `engine_overrides` 的一個維度（如 `topology_mode: "hypergraph"|"graph"`），還是維持現狀由 Hold 層內部決定——這牽涉到 CLAUDE.md「Hold is the hypergraph container」的既定架構邊界，開放給使用者選等於把內部拓撲決策外部化，需要先確認這不會破壞 Hold/bay 分離原則。

Sources:
- [Pipelines | Haystack Documentation](https://docs.haystack.deepset.ai/docs/pipelines)
- [Configuring Haystack Pipelines with YAML](https://medium.com/deepset-ai/configuring-haystack-pipelines-with-yaml-ca4b07572fb8)
- [txtai - Workflow](https://neuml.github.io/txtai/workflow/)
- [txtai - Configuration](https://neuml.github.io/txtai/api/configuration/)
- [RunnableConfigurableFields — LangChain](https://api.python.langchain.com/en/latest/runnables/langchain_core.runnables.configurable.RunnableConfigurableFields.html)
