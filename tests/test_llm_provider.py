from fastapi.testclient import TestClient

from apps.api import main
from salva_core.llm import LLMProviderHealth, OmlxProviderAdapter, build_bounded_prompt


def test_build_bounded_prompt_truncates_content() -> None:
    bundle = build_bounded_prompt(
        "summarization",
        "system " + ("x" * 5000),
        "user " + ("y" * 8000),
        model_name="demo",
        max_tokens=256,
    )

    assert bundle.task == "summarization"
    assert len(bundle.system_prompt) <= 2200
    assert len(bundle.user_prompt) <= 4200
    assert bundle.model_name == "demo"


def test_omlx_provider_health_and_completion(monkeypatch) -> None:
    responses = {
        "GET https://omlx.example/v1/models": {"data": []},
        "POST https://omlx.example/v1/chat/completions": {
            "choices": [{"message": {"content": '{"summary":"ok","tags":["alpha"]}'}}]
        },
    }

    def fake_request(self, url, payload, method="POST"):
        key = f"{method} {url}"
        if key not in responses:
            raise AssertionError(f"unexpected request: {key}")
        return responses[key]

    monkeypatch.setattr(OmlxProviderAdapter, "_request_json", fake_request)

    provider = OmlxProviderAdapter(base_url="https://omlx.example", token="token", default_model="demo-model")
    health = provider.health_check()
    assert health.available is True
    assert health.base_url == "https://omlx.example"

    result = provider.complete(
        build_bounded_prompt(
            "summarization",
            "system prompt",
            "user prompt",
            model_name="demo-model",
        )
    )
    assert result.available is True
    assert result.content is not None


def test_llm_api_endpoints(monkeypatch) -> None:
    monkeypatch.setattr(
        main,
        "probe_omlx_health",
        lambda model_name=None: LLMProviderHealth(
            name="omlx",
            available=True,
            base_url="http://127.0.0.1:8140",
            model_name=model_name or "gemma",
            latency_ms=1.0,
            message=None,
        ),
    )

    client = TestClient(main.app)
    providers = client.get("/v1/llm/providers")
    assert providers.status_code == 200
    assert providers.json()["total"] >= 1

    health = client.get("/v1/llm/health")
    assert health.status_code == 200
    assert health.json()["available"] is True
