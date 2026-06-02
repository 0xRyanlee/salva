from __future__ import annotations

import json
import os
from typing import Any

from salva_core.llm import build_bounded_prompt, complete_with_omlx
from salva_core.mode_resolver import resolve_experience_plan
from salva_core.schemas import (
    ClarificationQuestion,
    DiscoveryRequest,
    PlannerRequest,
    PlannerResponse,
    PrepromptResult,
    ResearchPlan,
    TopologyProbeResult,
    TopologyRoutePlan,
)
from salva_core.topology import plan_route, probe_topology


def build_planner_response(payload: PlannerRequest) -> PlannerResponse:
    probe = probe_topology(
        payload.discovery,
        caller_preset=payload.caller_preset,
        probe_budget=payload.question_budget,
    )
    route_plan = plan_route(
        payload.discovery,
        caller_preset=payload.caller_preset,
        probe_budget=payload.question_budget,
        probe=probe,
    )
    experience_plan = resolve_experience_plan(payload.discovery, topology_plan=route_plan)
    preprompt = build_preprompt(
        payload.discovery,
        probe=probe,
        route_plan=route_plan,
        question_budget=payload.question_budget,
        allow_llm=payload.allow_llm_preprompt,
    )
    plan = build_research_plan(
        payload.discovery,
        route_plan=route_plan,
        experience_profile=experience_plan.profile,
        preprompt=preprompt,
    )
    return PlannerResponse(
        probe=probe,
        route_plan=route_plan,
        preprompt=preprompt,
        plan=plan,
        experience_plan=experience_plan,
    )


def build_preprompt(
    discovery: DiscoveryRequest,
    probe: TopologyProbeResult,
    route_plan: TopologyRoutePlan,
    question_budget: int,
    allow_llm: bool,
) -> PrepromptResult:
    ambiguity_score = _ambiguity_score(discovery, probe, route_plan)
    risk_level = _risk_level(discovery, probe, route_plan, ambiguity_score)
    clarification_needed = ambiguity_score >= 0.45 or risk_level == "high"
    normalized_goal = _normalized_goal(discovery, probe, route_plan)
    assumptions_if_skip = _default_assumptions(discovery, route_plan)
    clarifying_questions = _rule_based_questions(
        discovery,
        probe,
        route_plan,
        budget=question_budget,
    )
    llm_used = False
    llm_model = None
    llm_message = None

    if allow_llm and clarification_needed and _should_use_llm_preprompt():
        llm_result = _llm_preprompt(
            discovery=discovery,
            normalized_goal=normalized_goal,
            ambiguity_score=ambiguity_score,
            risk_level=risk_level,
            budget=question_budget,
        )
        llm_used = llm_result["used"]
        llm_model = llm_result["model"]
        llm_message = llm_result["message"]
        if llm_result["questions"]:
            clarifying_questions = llm_result["questions"][:question_budget]
        if llm_result["normalized_goal"]:
            normalized_goal = llm_result["normalized_goal"]
        if llm_result["assumptions_if_skip"]:
            assumptions_if_skip = llm_result["assumptions_if_skip"]
        if llm_result["ambiguity_score"] is not None:
            ambiguity_score = float(llm_result["ambiguity_score"])
        if llm_result["risk_level"]:
            risk_level = llm_result["risk_level"]
        clarification_needed = bool(llm_result["clarification_needed"])

    return PrepromptResult(
        clarification_needed=clarification_needed,
        clarification_mode="agent" if clarification_needed else "rule",
        ambiguity_score=round(float(ambiguity_score), 2),
        risk_level=risk_level,
        normalized_goal=normalized_goal,
        clarifying_questions=clarifying_questions,
        assumptions_if_skip=assumptions_if_skip,
        llm_used=llm_used,
        llm_model=llm_model,
        llm_message=llm_message,
    )


def build_research_plan(
    discovery: DiscoveryRequest,
    route_plan: TopologyRoutePlan,
    experience_profile: str,
    preprompt: PrepromptResult,
) -> ResearchPlan:
    round_budget = _round_budget(route_plan.topology, discovery.max_results, preprompt)
    round_goals = _round_goals(route_plan.topology, route_plan.recommended_route, round_budget)
    completeness_target, confidence_target = _targets(route_plan.topology, preprompt)
    replan_triggers = _replan_triggers(route_plan.topology, preprompt)
    stop_conditions = _stop_conditions(round_budget, completeness_target, confidence_target, preprompt)
    notes = [
        f"topology={route_plan.topology}",
        f"clarification_needed={preprompt.clarification_needed}",
        f"ambiguity_score={preprompt.ambiguity_score}",
    ]
    return ResearchPlan(
        topology=route_plan.topology,
        recommended_route=route_plan.recommended_route,
        experience_profile=experience_profile,
        clarification_mode=preprompt.clarification_mode,
        round_budget=round_budget,
        round_goals=round_goals,
        completeness_target=completeness_target,
        confidence_target=confidence_target,
        source_pack=list(route_plan.source_pack),
        strategy_bias=list(route_plan.strategy_bias),
        fanout_policy=route_plan.fanout_policy,
        merge_policy=route_plan.merge_policy,
        replan_triggers=replan_triggers,
        stop_conditions=stop_conditions,
        notes=notes,
    )


def _round_budget(topology: str, max_results: int, preprompt: PrepromptResult) -> int:
    if topology in {"structured", "vertical"}:
        budget = 2
    elif topology in {"concentrated", "semantic_union"}:
        budget = 3
    elif topology in {"broad", "distributed", "mixed"}:
        budget = 4
    else:
        budget = 1
    if max_results >= 100:
        budget += 1
    if preprompt.clarification_needed:
        budget += 1
    return min(5, max(1, budget))


def _round_goals(topology: str, route_name: str, round_budget: int) -> list[str]:
    goals: list[str] = []
    if round_budget >= 1:
        goals.append(f"round1: probe seed space for {topology}")
    if round_budget >= 2:
        goals.append(f"round2: route via {route_name} and expand signal")
    if round_budget >= 3:
        goals.append("round3: dedupe and confirm evidence")
    if round_budget >= 4:
        goals.append("round4: cross-source diversification")
    if round_budget >= 5:
        goals.append("round5: final confidence sweep")
    return goals[:round_budget]


def _targets(topology: str, preprompt: PrepromptResult) -> tuple[float, float]:
    if topology in {"structured", "vertical"}:
        base = (0.8, 0.75)
    elif topology in {"concentrated", "semantic_union"}:
        base = (0.75, 0.72)
    elif topology in {"broad", "distributed", "mixed"}:
        base = (0.68, 0.65)
    else:
        base = (0.6, 0.58)
    if preprompt.clarification_needed:
        base = (min(0.9, base[0] + 0.05), min(0.88, base[1] + 0.05))
    return base


def _replan_triggers(topology: str, preprompt: PrepromptResult) -> list[str]:
    triggers = [
        "source_success_rate < 0.4",
        "qualified_rate < 0.15",
        "noise_rate > 0.5",
    ]
    if topology in {"broad", "distributed", "mixed"}:
        triggers.append("clarification_needed still true after round1")
    if preprompt.ambiguity_score >= 0.6:
        triggers.append("ambiguity_score remains high")
    return triggers


def _stop_conditions(
    round_budget: int,
    completeness_target: float,
    confidence_target: float,
    preprompt: PrepromptResult,
) -> list[str]:
    conditions = [
        f"round_budget reached ({round_budget})",
        f"confidence >= {confidence_target:.2f}",
        f"completeness >= {completeness_target:.2f}",
        "entity consensus stable",
    ]
    if preprompt.clarification_needed:
        conditions.insert(0, "clarifying question answered or skipped with assumptions")
    return conditions


def _normalized_goal(
    discovery: DiscoveryRequest,
    probe: TopologyProbeResult,
    route_plan: TopologyRoutePlan,
) -> dict[str, Any]:
    return {
        "objective": discovery.objective,
        "market": discovery.intent.market,
        "industry": discovery.intent.industry,
        "product": discovery.intent.product,
        "role": discovery.intent.role,
        "output_profile": discovery.output_profile,
        "topology": probe.topology,
        "recommended_route": route_plan.recommended_route,
        "source_pack": list(route_plan.source_pack),
    }


def _default_assumptions(discovery: DiscoveryRequest, route_plan: TopologyRoutePlan) -> list[str]:
    assumptions = []
    if discovery.objective in {"find_market_activity", "find_partnership_signals"}:
        assumptions.append("default_to_cross_source_signal_collection")
    if route_plan.topology in {"broad", "distributed", "mixed"}:
        assumptions.append("default_to_multi_round_search")
    if route_plan.topology in {"structured", "vertical"}:
        assumptions.append("default_to_high_precision_source_pack")
    if not discovery.intent.constraints.get("time_window"):
        assumptions.append("default_time_window_last_6_months")
    if not discovery.intent.domain_hints:
        assumptions.append("default_without_custom_domain_hints")
    return assumptions


def _rule_based_questions(
    discovery: DiscoveryRequest,
    probe: TopologyProbeResult,
    route_plan: TopologyRoutePlan,
    budget: int,
) -> list[ClarificationQuestion]:
    questions: list[ClarificationQuestion] = []
    if probe.topology in {"broad", "distributed", "mixed"}:
        questions.append(
            ClarificationQuestion(
                key="output_shape",
                question="你要的是清單、摘要、比較矩陣，還是可執行建議？",
                rationale="高發散 topology 需要先鎖定輸出形狀。",
                impact="影響 planner 是否偏向多輪彙整或單輪快答。",
            )
        )
    if discovery.objective in {"find_companies", "find_market_activity", "find_partnership_signals"}:
        questions.append(
            ClarificationQuestion(
                key="precision_vs_coverage",
                question="你要偏高準確還是高覆蓋？",
                rationale="這會直接影響 fanout 與 merge policy。",
                impact="影響 round_budget 與 source pack 擴張程度。",
            )
        )
    if not discovery.intent.constraints.get("time_window"):
        questions.append(
            ClarificationQuestion(
                key="time_window",
                question="要限制在最近幾個月或特定時間窗嗎？",
                rationale="沒有時間窗時，結果容易過寬。",
                impact="影響 source freshness 與 stop conditions。",
            )
        )
    if not discovery.intent.domain_hints and route_plan.topology in {"structured", "vertical"}:
        questions.append(
            ClarificationQuestion(
                key="source_preferences",
                question="你有特定優先來源嗎，例如官網、職缺站、媒體或社群？",
                rationale="結構化場景對 source pack 很敏感。",
                impact="影響 source_pack 與 route selection。",
            )
        )
    if discovery.intent.role is None and discovery.intent.product is None:
        questions.append(
            ClarificationQuestion(
                key="focus_axis",
                question="這次更重視角色、產品、公司，還是市場信號？",
                rationale="缺少 focus axis 時，planner 會偏保守。",
                impact="影響 route 和 experience profile 的選擇。",
            )
        )
    return questions[:budget]


def _ambiguity_score(discovery: DiscoveryRequest, probe, route_plan) -> float:
    score = 0.1
    if not discovery.intent.product:
        score += 0.12
    if not discovery.intent.role:
        score += 0.12
    if not discovery.intent.extra_keywords:
        score += 0.1
    if not discovery.intent.domain_hints:
        score += 0.08
    if not discovery.intent.constraints.get("time_window"):
        score += 0.05
    if probe.topology in {"broad", "distributed", "mixed"}:
        score += 0.18
    if probe.topology == "semantic_union":
        score += 0.12
    if probe.confidence < 0.7:
        score += 0.12
    if route_plan.fanout_policy != "low_fanout":
        score += 0.05
    return min(1.0, round(score, 2))


def _risk_level(discovery: DiscoveryRequest, probe, route_plan, ambiguity_score: float) -> str:
    if discovery.objective in {"find_market_activity", "find_partnership_signals"}:
        return "high" if ambiguity_score >= 0.5 else "medium"
    if probe.topology in {"broad", "distributed", "mixed"}:
        return "high" if ambiguity_score >= 0.55 else "medium"
    if route_plan.topology in {"structured", "vertical"} and ambiguity_score < 0.4:
        return "low"
    return "medium" if ambiguity_score >= 0.45 else "low"


def _should_use_llm_preprompt() -> bool:
    return os.getenv("SALVA_PLANNER_USE_LLM", "").strip().lower() in {"1", "true", "yes", "on"}


def _llm_preprompt(
    discovery: DiscoveryRequest,
    normalized_goal: dict[str, Any],
    ambiguity_score: float,
    risk_level: str,
    budget: int,
) -> dict[str, Any]:
    system_prompt = (
        "You are a planning assistant for a retrieval runtime. "
        "Return strict JSON only with keys: clarification_needed, ambiguity_score, risk_level, "
        "normalized_goal, questions, assumptions_if_skip. "
        "Questions must be concrete and at most 3. "
        "Never include markdown."
    )
    user_prompt = json.dumps(
        {
            "objective": discovery.objective,
            "intent": discovery.intent.model_dump(mode="json"),
            "output_profile": discovery.output_profile,
            "probe_topology": normalized_goal["topology"],
            "recommended_route": normalized_goal["recommended_route"],
            "ambiguity_score": ambiguity_score,
            "risk_level": risk_level,
            "question_budget": budget,
        },
        ensure_ascii=False,
        indent=2,
    )
    bundle = build_bounded_prompt(
        task="output_shaping",
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=400,
        temperature=0.2,
    )
    result = complete_with_omlx(bundle)
    if not result.available or not result.content:
        return {"used": False, "model": None, "message": result.message, "questions": [], "normalized_goal": {}, "assumptions_if_skip": [], "ambiguity_score": None, "risk_level": None, "clarification_needed": None}
    parsed = _parse_json_object(result.content)
    if not parsed:
        return {"used": False, "model": result.model_name, "message": result.message or "llm output was not valid JSON", "questions": [], "normalized_goal": {}, "assumptions_if_skip": [], "ambiguity_score": None, "risk_level": None, "clarification_needed": None}
    questions = []
    raw_questions = parsed.get("questions", [])
    if isinstance(raw_questions, list):
        for idx, item in enumerate(raw_questions):
            if isinstance(item, str) and item.strip():
                questions.append(
                    ClarificationQuestion(
                        key=f"llm_{idx}",
                        question=item.strip(),
                        rationale="LLM-generated clarification question.",
                        impact="Helps normalize the request before planning.",
                    )
                )
    assumptions = [str(item).strip() for item in parsed.get("assumptions_if_skip", []) if str(item).strip()] if isinstance(parsed.get("assumptions_if_skip"), list) else []
    normalized = parsed.get("normalized_goal") if isinstance(parsed.get("normalized_goal"), dict) else {}
    return {
        "used": True,
        "model": result.model_name,
        "message": result.message,
        "questions": questions,
        "normalized_goal": normalized,
        "assumptions_if_skip": assumptions,
        "ambiguity_score": parsed.get("ambiguity_score", ambiguity_score),
        "risk_level": parsed.get("risk_level", risk_level),
        "clarification_needed": parsed.get("clarification_needed", True),
    }


def _parse_json_object(text: str) -> dict[str, Any] | None:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            data = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, dict) else None
