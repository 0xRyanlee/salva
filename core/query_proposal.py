"""Bounded LLM query-proposal step for the multi-round retrieval loop.

Amendment 2026-07-21 (CLAUDE.md, "Deterministic Pipeline First"): the
deterministic retrieval loop may optionally consult a scoped, JSON-bounded
LLM call that proposes ONE follow-up search query when the accumulated
candidate pool looks thin. It never re-plans strategy, never reasons freely,
and never replaces `core/keyword_graph.py`'s deterministic expansion -- its
only output is {need_followup, query}. Motivated by the CNCF founders case:
deterministic multi-round retrieval fetched a Wikipedia secondary list and
missed the original 2015 press release; a freely-searching agent found it by
searching further. The LLM client is injected (defaults to the local omlx
endpoint) so this is unit-testable offline and degrades to "no follow-up"
whenever the LLM is unreachable or returns something unparseable.
"""
from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field

from core.types import Intent
from salva_core.llm import (
    LLMCompletionResult,
    LLMPromptBundle,
    build_bounded_prompt,
    complete_with_omlx,
)

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
        # Malformed "yes but no query given" -- never invent a query, just no-op.
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

    runner: CompleteFn = complete if complete is not None else complete_with_omlx
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
