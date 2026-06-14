"""
LLM enrichment via OMLX (local OpenAI-compatible endpoint).

This adapter uses bounded prompts so enrichment stays scoped and predictable.
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Literal, cast

from salva_core.llm import DEFAULT_OMLX_TIMEOUT, build_bounded_prompt, complete_with_omlx
from salva_core.schemas import DiscoveryRequest

logger = logging.getLogger("salva.enrichment.omlx")

LLMTask = Literal["expansion", "extraction", "summarization", "output_shaping"]


_SYSTEM_PROMPTS: dict[str, str] = {
    "events": (
        "你是活動分析 AI。只根據提供內容輸出 JSON："
        '{"type":"meetup|workshop|event|popup","type_confidence":0.0-1.0,'
        '"tags":["標籤"],"summary":"50-100字繁中摘要",'
        '"target_audience":"目標受眾","language":"zh-TW|en","city":"城市"}'
    ),
    "bd_leads": (
        "You are a bounded B2B lead analyst. Return JSON only: "
        '{"industry":"<detected industry>","role":"reseller|partner|integrator|distributor",'
        '"market":"<detected market region>","confidence":0.0-1.0,'
        '"summary":"50-word english summary","has_contact":true|false}'
    ),
}

_USER_PROMPTS: dict[str, str] = {
    "events": "分析活動：\n標題：{title}\n描述：{description}\n地點：{location}\n時間：{starts_at}\n費用：{price}",
    "bd_leads": "Analyze company:\nName: {title}\nWebsite: {source_url}\nSnippet: {description}",
}

_OBJECTIVE_PROMPT_HINTS: dict[str, str] = {
    "find_events": "Focus on event signals, date windows, venues, speakers, organizers, and audience fit.",
    "find_exhibitors": "Focus on exhibitor intent, booth presence, product category fit, and event participation signals.",
    "find_leads": "Focus on lead qualification, role fit, contact availability, and buying or distribution intent.",
    "find_companies": "Focus on company identity, business scope, market position, and collaboration signals.",
    "find_market_activity": "Focus on market movement, announcements, launches, hiring, and recent activity signals.",
    "find_partnership_signals": "Focus on partnership evidence, co-marketing, joint events, mutual mentions, and integration signals.",
}


def enrich(domain: str, fields: dict, model: str | None = None, request: DiscoveryRequest | None = None) -> dict | None:
    system, user_template, task = _select_prompt_bundle(domain, request)
    user = user_template.format_map({k: (v or "") for k, v in fields.items()})

    # Get timeout and retry config from request
    timeout = DEFAULT_OMLX_TIMEOUT
    max_retries = 0
    
    if request and request.enrichment:
        timeout = request.enrichment.omlx_timeout or DEFAULT_OMLX_TIMEOUT
        max_retries = request.enrichment.omlx_max_retries or 0

    bundle = build_bounded_prompt(
        cast(LLMTask, task),
        system,
        user,
        model_name=model,
        max_tokens=420,
        temperature=0.2,
    )
    
    # Retry loop with exponential backoff
    last_error = None
    for attempt in range(max(1, max_retries + 1)):
        try:
            result = complete_with_omlx(bundle, timeout=timeout)
            if result.available and result.content:
                return _parse_json(result.content)
            last_error = result.message or "no content"
        except Exception as e:
            last_error = str(e)
        
        if attempt < max_retries:
            # Exponential backoff: 1s, 2s, 4s...
            sleep_time = 2 ** attempt
            logger.warning(f"OMLX call failed (attempt {attempt + 1}/{max_retries + 1}), retrying in {sleep_time}s: {last_error}")
            time.sleep(sleep_time)
    
    logger.warning(f"OMLX call failed after {max_retries + 1} attempts: {last_error}")
    return None


def enrich_batch(
    domain: str,
    items: list[dict],
    model: str | None = None,
    delay: float = 0.1,
    request: DiscoveryRequest | None = None,
) -> list[dict | None]:
    import time

    results = []
    for item in items:
        results.append(enrich(domain, item, model, request=request))
        if delay > 0:
            time.sleep(delay)
    return results


def _select_prompt_bundle(domain: str, request: DiscoveryRequest | None) -> tuple[str, str, str]:
    base_system = _SYSTEM_PROMPTS.get(domain, _SYSTEM_PROMPTS["events"])
    base_user = _USER_PROMPTS.get(domain, _USER_PROMPTS["events"])
    objective_hint = _OBJECTIVE_PROMPT_HINTS.get(request.objective, "") if request else ""
    output_hint = ""
    if request:
        output_hint = _output_profile_hint(request.output_profile)

    system = "\n".join(part for part in [base_system, objective_hint, output_hint] if part)
    task = _task_for_request(domain, request)
    return system, base_user, task


def _task_for_request(domain: str, request: DiscoveryRequest | None) -> LLMTask:
    if request is None:
        return cast(LLMTask, "summarization" if domain == "events" else "extraction")
    if request.objective in {"find_events", "find_exhibitors"}:
        return cast(LLMTask, "summarization")
    if request.objective in {"find_market_activity", "find_partnership_signals"}:
        return cast(LLMTask, "output_shaping")
    return cast(LLMTask, "extraction")


def _output_profile_hint(output_profile: str) -> str:
    hints = {
        "lead": "Return lead-focused signals and keep the summary compact.",
        "crm_contact": "Prioritize contactability and CRM-friendly fields.",
        "event": "Return event-specific metadata and keep ambiguity low.",
        "company": "Return concise company-level descriptors and evidence hints.",
        "company_profile": "Prefer company profile shaping and structured field extraction.",
        "activity_signal": "Emphasize market signals and momentum instead of generic summaries.",
    }
    return hints.get(output_profile, "")


def _parse_json(text: str) -> dict | None:
    block = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if block:
        text = block.group(1)
    else:
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            text = m.group()
    try:
        return json.loads(text)
    except Exception:
        return None
