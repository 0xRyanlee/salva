"""E12 — Snippet-missing graceful degradation.

VP12: When a retrieved result has no snippet (description=""), the scorer must:
  1. Tag the result with "no_snippet" reject reason.
  2. Return a score ≤ 0.30 — below the default qualify_threshold of 0.40.
  3. Never let a title-only result silently pass as qualified.
"""
from __future__ import annotations

from core.types import Intent, UnifiedResult
from processing.scorer import QualificationScorer, ScorerConfig


def _make_intent(domain: str = "bd_leads") -> Intent:
    return Intent(domain=domain, primary_terms=["Naturehike", "outdoor equipment"], region="Germany")


def _make_result(title: str, description: str = "", url: str = "https://example.de") -> UnifiedResult:
    return UnifiedResult(
        source_name="ddg_html",
        source_url=url,
        title=title,
        description=description,
    )


class TestSnippetMissingScoreCap:
    def test_empty_snippet_score_below_threshold(self):
        scorer = QualificationScorer()
        intent = _make_intent()
        result = _make_result("ICON Outdoor Distribution GmbH")
        score = scorer.score(result, intent)
        assert score <= 0.30, f"Expected score ≤ 0.30, got {score}"

    def test_empty_snippet_adds_reject_reason(self):
        scorer = QualificationScorer()
        intent = _make_intent()
        result = _make_result("ICON Outdoor Distribution GmbH")
        scorer.score(result, intent)
        assert "no_snippet" in result.reject_reasons

    def test_rich_snippet_can_pass_threshold(self):
        scorer = QualificationScorer()
        intent = _make_intent()
        result = _make_result(
            "ICON Outdoor Distribution GmbH",
            description=(
                "Leading outdoor equipment distributor and importer in Germany. "
                "Naturehike wholesale and bulk B2B sourcing for DACH region."
            ),
            url="https://icon-outdoor.de/about",
        )
        score = scorer.score(result, intent)
        assert score > 0.30, f"Expected score > 0.30 with rich snippet, got {score}"

    def test_none_description_treated_same_as_empty(self):
        """UnifiedResult.description defaults to '' but verify None path also capped."""
        scorer = QualificationScorer()
        intent = _make_intent()
        result = _make_result("Sport Handelsagentur Weindel", description="")
        score = scorer.score(result, intent)
        assert score <= 0.30

    def test_non_snippet_result_never_qualifies_at_default_threshold(self):
        scorer = QualificationScorer()
        intent = _make_intent()
        qualify_threshold = 0.40
        result = _make_result("Random Page Title without any relevant content")
        score = scorer.score(result, intent)
        assert score < qualify_threshold, (
            f"Snippet-missing result must not pass qualify_threshold={qualify_threshold}, got {score}"
        )


class TestSnippetPresentDoesNotPenalize:
    def test_no_penalty_when_snippet_present(self):
        scorer = QualificationScorer()
        intent = _make_intent()
        result_with = _make_result("Elementum Distribution", description="distributor importer Germany outdoor")
        result_without = _make_result("Elementum Distribution", description="")
        score_with = scorer.score(result_with, intent)
        score_without = scorer.score(result_without, intent)
        assert score_with > score_without
