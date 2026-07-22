"""Scoped LLM rerank -- production form of the accumulate-then-rerank pipeline
that previously lived only in experiments/salva_v2/pipelines/accumulate_llm_rerank.md.

The retrieval-derived confidence ranking (processing/confidence.py) orders and
bounds the candidate pool; this stage hands the top-K (already ordered, not an
all-or-nothing dump) to a bounded LLM call that makes the final relevance
judgment and returns a filtered {name, url, claim} list. The LLM client is
injected (defaults to the local omlx endpoint) so it is unit-testable offline
and degrades to a confidence-ordered passthrough when no LLM is reachable.
"""
from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field

from salva_core.llm import (
    LLMCompletionResult,
    LLMPromptBundle,
    build_bounded_prompt,
    complete_with_omlx,
)

CompleteFn = Callable[[LLMPromptBundle], LLMCompletionResult]


@dataclass
class RerankCandidate:
    name: str
    url: str
    snippet: str
    confidence: float


@dataclass
class RerankResult:
    kept: list[dict[str, str]]
    llm_available: bool
    dropped_count: int
    notes: list[str] = field(default_factory=list)


_SYSTEM = (
    "You filter and rank raw web search candidates for a business research "
    "question. Some are genuinely relevant; many are noise that merely matched "
    "a keyword. Return JSON only."
)

# v2 prompt from accumulate_llm_rerank.md -- the primary-source cross-verification
# instruction is what closed multihop-01's precision gap.
_TASK = (
    "Question: {question}\n"
    "Search intent: market={market}, industry={industry}, objective={objective}, "
    "keywords={keywords}\n\n"
    "Candidates (confidence-ordered; judge each on merit):\n{candidates}\n\n"
    "Identify which candidates are genuinely relevant/useful. Discard noise. "
    "Merge near-duplicates referring to the same entity.\n"
    "For factual roster/membership claims, secondary summaries (Wikipedia, "
    "aggregators) can repeat outdated lists -- prefer a candidate backed by the "
    "entity's own primary source when one is present in the list.\n"
    'Return JSON: {{"kept": [{{"name": "...", "url": "...", "claim": "one sentence"}}]}}. '
    "If none are relevant, return an empty kept list rather than forcing a match."
)


def _format_candidates(candidates: list[RerankCandidate]) -> str:
    lines = []
    for index, candidate in enumerate(candidates, start=1):
        snippet = candidate.snippet.replace("\n", " ")[:240]
        lines.append(f"{index}. {candidate.name} | {candidate.url} | {snippet}")
    return "\n".join(lines)


def _parse_kept(content: str) -> list[dict[str, str]] | None:
    block = re.search(r"\{[\s\S]*\}", content)
    text = block.group() if block else content
    try:
        data = json.loads(text)
    except Exception:
        return None
    kept = data.get("kept") if isinstance(data, dict) else None
    if not isinstance(kept, list):
        return None
    cleaned: list[dict[str, str]] = []
    for item in kept:
        if isinstance(item, dict) and item.get("url"):
            cleaned.append({
                "name": str(item.get("name", "")),
                "url": str(item["url"]),
                "claim": str(item.get("claim", "")),
            })
    return cleaned


def scoped_rerank(
    candidates: list[RerankCandidate],
    *,
    question: str,
    market: str = "",
    industry: str = "",
    objective: str = "",
    keywords: list[str] | None = None,
    model: str | None = None,
    max_candidates: int = 25,
    complete: CompleteFn | None = None,
) -> RerankResult:
    scoped = candidates[:max_candidates]
    if not scoped:
        return RerankResult(kept=[], llm_available=False, dropped_count=0, notes=["empty_pool"])

    runner: CompleteFn = complete if complete is not None else complete_with_omlx
    user = _TASK.format(
        question=question,
        market=market,
        industry=industry,
        objective=objective,
        keywords=", ".join(keywords or []),
        candidates=_format_candidates(scoped),
    )
    bundle = build_bounded_prompt(
        "output_shaping", _SYSTEM, user, model_name=model, max_tokens=700, temperature=0.1
    )

    result = runner(bundle)
    if not result.available or not result.content:
        # Passthrough: keep the confidence-ordered pool as-is so the pipeline
        # still returns a ranked result when no LLM is reachable.
        kept = [{"name": c.name, "url": c.url, "claim": ""} for c in scoped]
        return RerankResult(
            kept=kept, llm_available=False, dropped_count=0,
            notes=["llm_unavailable_passthrough"],
        )

    parsed = _parse_kept(result.content)
    if parsed is None:
        kept = [{"name": c.name, "url": c.url, "claim": ""} for c in scoped]
        return RerankResult(
            kept=kept, llm_available=True, dropped_count=0,
            notes=["unparseable_llm_output_passthrough"],
        )

    return RerankResult(
        kept=parsed,
        llm_available=True,
        dropped_count=max(0, len(scoped) - len(parsed)),
    )
