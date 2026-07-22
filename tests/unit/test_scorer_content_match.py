"""Regression coverage for _content_match's BM25 + semantic-vector hybrid.

Card: salva-p7-embedding-backend-default. Before this change, _content_match
was a naive substring hit-count (present/absent per primary_term, no TF, no
tolerance for word order). These tests pin the properties that changed:
term frequency now matters, and multi-word terms match on constituent tokens
rather than requiring an exact phrase.
"""
from __future__ import annotations

from core.types import Intent
from processing.scorer import QualificationScorer


def test_content_match_rewards_term_frequency_over_single_occurrence() -> None:
    intent = Intent(domain="general", primary_terms=["naturehike"])
    single = QualificationScorer._content_match("naturehike tent supplier", intent)
    repeated = QualificationScorer._content_match(
        "naturehike naturehike naturehike tent supplier naturehike outdoor", intent
    )
    assert repeated > single


def test_content_match_matches_multiword_term_via_tokens_not_exact_phrase() -> None:
    """'outdoor equipment' as a naive substring check would score 0.0 against
    text where the words appear but not adjacently -- token-level BM25 should
    still register a nonzero match."""
    intent = Intent(domain="general", primary_terms=["outdoor equipment"])
    text = "distributor of outdoor gear and camping equipment in Germany"
    score = QualificationScorer._content_match(text, intent)
    assert score > 0.0


def test_content_match_bounded_between_zero_and_one() -> None:
    intent = Intent(
        domain="general",
        primary_terms=["naturehike", "outdoor", "distributor", "wholesale"],
    )
    text = (
        "naturehike naturehike naturehike outdoor outdoor "
        "distributor wholesale wholesale wholesale"
    )
    score = QualificationScorer._content_match(text, intent)
    assert 0.0 <= score <= 1.0


def test_content_match_empty_text_is_zero() -> None:
    intent = Intent(domain="general", primary_terms=["naturehike"])
    assert QualificationScorer._content_match("", intent) == 0.0


def test_content_match_no_primary_terms_is_zero() -> None:
    intent = Intent(domain="general", primary_terms=[])
    assert QualificationScorer._content_match("some text here", intent) == 0.0


def test_content_match_unrelated_text_scores_lower_than_matching_text() -> None:
    intent = Intent(domain="general", primary_terms=["naturehike", "outdoor equipment"])
    matching = QualificationScorer._content_match(
        "naturehike outdoor equipment distributor in Germany", intent
    )
    unrelated = QualificationScorer._content_match(
        "quarterly earnings report for a semiconductor foundry", intent
    )
    assert matching > unrelated
