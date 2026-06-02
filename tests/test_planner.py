from __future__ import annotations

import json

from fastapi.testclient import TestClient

from apps.api import main
from salva_core.llm import LLMCompletionResult
from salva_core.planner import build_planner_response
from salva_core.schemas import DiscoveryIntent, DiscoveryRequest, PlannerRequest, RetrievalPolicy


def test_planner_builds_round_budget_and_clarification_policy() -> None:
    request = DiscoveryRequest(
        objective="find_companies",
        intent=DiscoveryIntent(
            market="Taipei",
            industry="AI",
        ),
        retrieval=RetrievalPolicy(),
    )

    response = build_planner_response(PlannerRequest(discovery=request, question_budget=3))

    assert response.probe.topology == "vertical"
    assert response.route_plan.recommended_route == "company_research"
    assert response.preprompt.clarification_needed is True
    assert response.preprompt.ambiguity_score >= 0.45
    assert response.preprompt.clarifying_questions
    assert response.plan.round_budget >= 2
    assert response.plan.round_goals
    assert response.plan.stop_conditions


def test_planner_request_can_be_built_from_objective_and_intent() -> None:
    request = PlannerRequest(
        objective="find_companies",
        intent=DiscoveryIntent(
            market="Taipei",
            industry="AI",
        ),
        question_budget=3,
    )

    assert request.discovery is not None
    assert request.discovery.objective == "find_companies"
    assert request.discovery.intent.market == "Taipei"
    assert request.discovery.output_profile == "lead"


def test_planner_can_use_llm_preprompt(monkeypatch) -> None:
    monkeypatch.setenv("SALVA_PLANNER_USE_LLM", "1")

    def fake_complete(bundle):
        return LLMCompletionResult(
            provider_name="omlx",
            model_name="demo-model",
            task=bundle.task,
            content=json.dumps(
                {
                    "clarification_needed": True,
                    "ambiguity_score": 0.82,
                    "risk_level": "high",
                    "normalized_goal": {
                        "objective": "find_companies",
                        "output_shape": "comparison_matrix",
                    },
                    "questions": [
                        "你要的是公司清單、比較矩陣，還是摘要？",
                        "時間窗要不要限制在最近 6 個月？",
                    ],
                    "assumptions_if_skip": ["default_to_last_6_months"],
                },
                ensure_ascii=False,
            ),
            available=True,
            latency_ms=12.3,
        )

    monkeypatch.setattr("salva_core.planner.complete_with_omlx", fake_complete)

    request = DiscoveryRequest(
        objective="find_companies",
        intent=DiscoveryIntent(
            market="Taipei",
            industry="AI",
        ),
        retrieval=RetrievalPolicy(),
    )

    response = build_planner_response(PlannerRequest(discovery=request, question_budget=2, allow_llm_preprompt=True))

    assert response.preprompt.llm_used is True
    assert response.preprompt.llm_model == "demo-model"
    assert response.preprompt.ambiguity_score == 0.82
    assert response.preprompt.clarification_needed is True
    assert len(response.preprompt.clarifying_questions) == 2
    assert response.preprompt.normalized_goal["output_shape"] == "comparison_matrix"


def test_planner_api_roundtrip() -> None:
    client = TestClient(main.app)
    response = client.post(
        "/v1/planner",
        json={
            "question_budget": 3,
            "allow_llm_preprompt": False,
            "objective": "find_companies",
            "intent": {
                "market": "Taipei",
                "industry": "AI",
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["probe"]["topology"] == "vertical"
    assert body["preprompt"]["clarification_needed"] is True
    assert body["plan"]["round_budget"] >= 2
