from datetime import UTC, datetime

from enrichment.rerank import RerankCandidate, scoped_rerank
from salva_core.llm import LLMCompletionResult


def _candidates(n: int = 3) -> list[RerankCandidate]:
    return [
        RerankCandidate(name=f"Cand {i}", url=f"https://c{i}.com", snippet="snip", confidence=1.0 - i * 0.1)
        for i in range(n)
    ]


def _completion(content: str | None, available: bool = True) -> LLMCompletionResult:
    return LLMCompletionResult(
        provider_name="stub", model_name="stub", task="output_shaping",
        content=content, available=available, checked_at=datetime.now(UTC),
    )


def test_rerank_filters_via_llm_json():
    def stub(_bundle):
        return _completion('{"kept": [{"name": "Cand 0", "url": "https://c0.com", "claim": "relevant"}]}')

    result = scoped_rerank(_candidates(3), question="who", complete=stub)
    assert result.llm_available is True
    assert len(result.kept) == 1
    assert result.kept[0]["url"] == "https://c0.com"
    assert result.dropped_count == 2


def test_rerank_passthrough_when_llm_unavailable():
    def stub(_bundle):
        return _completion(None, available=False)

    result = scoped_rerank(_candidates(3), question="who", complete=stub)
    assert result.llm_available is False
    assert len(result.kept) == 3
    assert "llm_unavailable_passthrough" in result.notes


def test_rerank_passthrough_on_unparseable_output():
    def stub(_bundle):
        return _completion("not json at all")

    result = scoped_rerank(_candidates(2), question="who", complete=stub)
    assert result.llm_available is True
    assert len(result.kept) == 2
    assert "unparseable_llm_output_passthrough" in result.notes


def test_rerank_caps_candidate_pool():
    captured: dict[str, object] = {}

    def stub(bundle):
        captured["bundle"] = bundle
        return _completion('{"kept": []}')

    scoped_rerank(_candidates(50), question="who", max_candidates=10, complete=stub)
    user_prompt = captured["bundle"].user_prompt  # type: ignore[attr-defined]
    assert "10. Cand 9" in user_prompt
    assert "11. Cand 10" not in user_prompt


def test_rerank_empty_pool():
    result = scoped_rerank([], question="who")
    assert result.kept == []
    assert "empty_pool" in result.notes
