from datetime import UTC, datetime

from core.query_proposal import PoolItem, propose_followup_query
from core.types import Intent
from salva_core.llm import LLMCompletionResult


def _pool(n: int = 3) -> list[PoolItem]:
    return [
        PoolItem(title=f"Item {i}", url=f"https://c{i}.com", snippet="snip")
        for i in range(n)
    ]


def _intent() -> Intent:
    return Intent(domain="companies", primary_terms=["CNCF", "founders"], region="global")


def _completion(content: str | None, available: bool = True) -> LLMCompletionResult:
    return LLMCompletionResult(
        provider_name="stub", model_name="stub", task="output_shaping",
        content=content, available=available, checked_at=datetime.now(UTC),
    )


def test_proposes_followup_query_from_llm_json():
    def stub(_bundle):
        return _completion(
            '{"need_followup": true, '
            '"query": "CNCF founding members 2015 press release site:cncf.io"}'
        )

    result = propose_followup_query(_pool(), _intent(), 0.1, complete=stub)
    assert result.llm_available is True
    assert result.need_followup is True
    assert result.query == "CNCF founding members 2015 press release site:cncf.io"


def test_no_followup_when_llm_says_pool_sufficient():
    def stub(_bundle):
        return _completion('{"need_followup": false, "query": ""}')

    result = propose_followup_query(_pool(), _intent(), 0.9, complete=stub)
    assert result.need_followup is False
    assert result.query is None


def test_no_followup_when_llm_unavailable():
    def stub(_bundle):
        return _completion(None, available=False)

    result = propose_followup_query(_pool(), _intent(), 0.1, complete=stub)
    assert result.llm_available is False
    assert result.need_followup is False
    assert result.query is None
    assert "llm_unavailable_no_followup" in result.notes


def test_no_followup_on_unparseable_output():
    def stub(_bundle):
        return _completion("not json at all")

    result = propose_followup_query(_pool(), _intent(), 0.1, complete=stub)
    assert result.llm_available is True
    assert result.need_followup is False
    assert "unparseable_llm_output_no_followup" in result.notes


def test_no_followup_when_need_true_but_query_missing():
    """Malformed 'yes but no query' -- never invent a query, just no-op."""
    def stub(_bundle):
        return _completion('{"need_followup": true, "query": ""}')

    result = propose_followup_query(_pool(), _intent(), 0.1, complete=stub)
    assert result.need_followup is False
    assert result.query is None


def test_empty_pool_short_circuits_without_calling_llm():
    called = {"n": 0}

    def stub(_bundle):
        called["n"] += 1
        return _completion('{"need_followup": true, "query": "x"}')

    result = propose_followup_query([], _intent(), 0.0, complete=stub)
    assert result.need_followup is False
    assert result.llm_available is False
    assert "empty_pool" in result.notes
    assert called["n"] == 0


def test_prompt_bounds_pool_to_max_items():
    captured: dict[str, object] = {}

    def stub(bundle):
        captured["bundle"] = bundle
        return _completion('{"need_followup": false, "query": ""}')

    propose_followup_query(_pool(20), _intent(), 0.1, max_pool_items=5, complete=stub)
    user_prompt = captured["bundle"].user_prompt  # type: ignore[attr-defined]
    assert "5. Item 4" in user_prompt
    assert "6. Item 5" not in user_prompt


def test_prompt_includes_saturation_and_domain():
    captured: dict[str, object] = {}

    def stub(bundle):
        captured["bundle"] = bundle
        return _completion('{"need_followup": false, "query": ""}')

    propose_followup_query(_pool(), _intent(), 0.25, complete=stub)
    user_prompt = captured["bundle"].user_prompt  # type: ignore[attr-defined]
    assert "0.25" in user_prompt
    assert "companies" in user_prompt
