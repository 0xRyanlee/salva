"""多輪檢索迴圈的 bounded LLM query-proposal 步驟。

Amendment 2026-07-21（CLAUDE.md，"Deterministic Pipeline First"）：決定論
檢索迴圈可以選擇性諮詢一個範圍受限、JSON-bounded 的 LLM 呼叫，在累積候選
池看起來太薄時提議「一個」追加搜尋查詢。它從不重新規劃策略、從不自由
推理，也從不取代 `core/keyword_graph.py` 的決定論式擴展——唯一輸出是
{need_followup, query}。動機來自 CNCF founders 案例：決定論式多輪檢索抓到
Wikipedia 的次要清單，卻漏掉 2015 年的原始新聞稿；一個自由搜尋的 agent
靠繼續搜尋找到了它。LLM client 是注入的（預設走
salva_core.llm_sidecar.resolve_llm_completion_fn()——BYOK 若有設定就優先，
否則走本機 sidecar CLI passthrough；2026-07-23 修訂，不再是本機 omlx），
所以可以離線做單元測試，LLM 連不上或回傳無法解析的內容時會降級成「不追加
查詢」。
"""
from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field

from core.types import Intent
from salva_core.llm import LLMCompletionResult, LLMPromptBundle, build_bounded_prompt
from salva_core.llm_sidecar import resolve_llm_completion_fn

CompleteFn = Callable[[LLMPromptBundle], LLMCompletionResult]


@dataclass
class PoolItem:
    title: str
    url: str
    snippet: str


@dataclass
class QueryProposal:
    need_followup: bool
    query: str | None
    llm_available: bool
    notes: list[str] = field(default_factory=list)


_SYSTEM = (
    "You review a partial web search result pool for a structured discovery "
    "task and decide whether ONE more, more targeted search query would help "
    "surface a primary source (e.g. an original press release, official "
    "filing, or first-party page) that the pool may be missing. You do not "
    "answer the underlying question and you do not propose a new search "
    "strategy -- you only decide whether to search once more and, if so, "
    "what to search for. Return JSON only."
)

_TASK = (
    "Discovery intent: domain={domain}, terms={terms}, region={region}\n"
    "Pool so far ({pool_size} candidates; corroboration_saturation={saturation:.2f} "
    "-- fraction of candidates multiple independent queries converged on, "
    "low means the pool is thin / likely secondary-source-only):\n{pool}\n\n"
    "Does this pool look like it is missing a primary source (e.g. only "
    "secondary summaries/aggregators like Wikipedia are present, or the pool "
    "is thin)? If yes, propose ONE more specific follow-up search query "
    "likely to surface the primary source directly. If the pool already "
    "looks sufficient, say no follow-up is needed.\n"
    'Return JSON: {{"need_followup": true|false, "query": "..."}}. '
    'If need_followup is false, query may be "".'
)


def _format_pool(pool: list[PoolItem], limit: int) -> str:
    lines = []
    for index, item in enumerate(pool[:limit], start=1):
        snippet = item.snippet.replace("\n", " ")[:180]
        lines.append(f"{index}. {item.title} | {item.url} | {snippet}")
    return "\n".join(lines) or "(empty)"


def _parse_proposal(content: str) -> tuple[bool, str | None] | None:
    block = re.search(r"\{[\s\S]*\}", content)
    text = block.group() if block else content
    try:
        data = json.loads(text)
    except Exception:
        return None
    if not isinstance(data, dict) or "need_followup" not in data:
        return None
    need = bool(data.get("need_followup"))
    query = data.get("query")
    query = query.strip() if isinstance(query, str) else ""
    if need and not query:
        # 格式錯誤：說要追加查詢卻沒給查詢字串——絕不自己編一個，直接 no-op。
        return False, None
    return need, (query if need else None)


def propose_followup_query(
    pool: list[PoolItem],
    intent: Intent,
    corroboration_saturation: float,
    *,
    model: str | None = None,
    max_pool_items: int = 12,
    complete: CompleteFn | None = None,
) -> QueryProposal:
    if not pool:
        return QueryProposal(
            need_followup=False, query=None, llm_available=False, notes=["empty_pool"]
        )

    runner: CompleteFn = complete if complete is not None else resolve_llm_completion_fn()
    user = _TASK.format(
        domain=intent.domain,
        terms=", ".join(intent.primary_terms),
        region=intent.region or "",
        pool_size=len(pool),
        saturation=corroboration_saturation,
        pool=_format_pool(pool, max_pool_items),
    )
    bundle = build_bounded_prompt(
        "output_shaping", _SYSTEM, user, model_name=model, max_tokens=200, temperature=0.1
    )

    result = runner(bundle)
    if not result.available or not result.content:
        return QueryProposal(
            need_followup=False, query=None, llm_available=False,
            notes=["llm_unavailable_no_followup"],
        )

    parsed = _parse_proposal(result.content)
    if parsed is None:
        return QueryProposal(
            need_followup=False, query=None, llm_available=True,
            notes=["unparseable_llm_output_no_followup"],
        )

    need, query = parsed
    return QueryProposal(need_followup=need, query=query, llm_available=True)
