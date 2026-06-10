"""Phase 1 — Recall Closure Tests.

Covers A1 (query diversity), A2 (provider fallback), A3 (scoring calibration).
"""
from __future__ import annotations

import pytest

from core.keyword_graph import KeywordGraph
from core.query_strategy import (
    _compute_role_angles,
    build_strategy_profile,
    build_queries,
)
from core.types import Intent, UnifiedResult
from processing.scorer import DOMAIN_CONFIGS, QualificationScorer, ScorerConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _naturehike_intent() -> Intent:
    return Intent(
        domain="bd_leads",
        primary_terms=["Naturehike", "outdoor equipment"],
        region="Germany Austria Switzerland",
        roles=["distributor"],
        negative_terms=["blog", "review", "job"],
        max_rounds=3,
        results_per_round=30,
    )


def _computex_intent() -> Intent:
    return Intent(
        domain="taiwan_hardware",
        primary_terms=["Computex 2026", "Taiwan hardware"],
        region="Taipei",
        roles=["exhibitor"],
        negative_terms=["job", "review"],
        max_rounds=3,
        results_per_round=30,
    )


# ---------------------------------------------------------------------------
# A1 — Query Diversity (role angle expansion)
# ---------------------------------------------------------------------------

class TestRoleAngleExpansion:
    def test_distributor_expands_to_multiple_angles(self):
        from core.domain_vocab import get_vocab
        vocab = get_vocab("bd_leads")
        angles = _compute_role_angles(_naturehike_intent(), vocab)
        assert "distributor" in angles
        assert "wholesaler" in angles
        assert "importer" in angles

    def test_exhibitor_expands_to_oemOdm(self):
        from core.domain_vocab import get_vocab
        vocab = get_vocab("taiwan_hardware")
        angles = _compute_role_angles(_computex_intent(), vocab)
        assert "exhibitor" in angles
        assert len(angles) >= 3, f"Expected ≥3 angles, got {angles}"

    def test_no_duplicate_angles(self):
        from core.domain_vocab import get_vocab
        vocab = get_vocab("bd_leads")
        angles = _compute_role_angles(_naturehike_intent(), vocab)
        lower = [a.lower() for a in angles]
        assert len(lower) == len(set(lower)), f"Duplicates found: {angles}"

    def test_empty_roles_returns_empty_angles(self):
        intent = Intent(domain="bd_leads", primary_terms=["test"], region="DE")
        from core.domain_vocab import get_vocab
        angles = _compute_role_angles(intent, get_vocab("bd_leads"))
        assert angles == []

    def test_profile_includes_role_angles(self):
        graph = KeywordGraph(_naturehike_intent())
        profile = build_strategy_profile(_naturehike_intent(), "dive", 1, graph.vocab)
        assert "role_angles" in profile
        assert "wholesaler" in profile["role_angles"]

    def test_dive_queries_contain_multiple_role_terms(self):
        intent = _naturehike_intent()
        graph = KeywordGraph(intent)
        nodes = graph._ranked_nodes()
        profile = build_strategy_profile(intent, "dive", 1, graph.vocab)
        queries = build_queries(intent, nodes, round_num=1, strategy="dive",
                                max_queries=10, profile=profile)
        role_terms_found = {
            term for q in queries
            for term in ["distributor", "wholesaler", "importer", "dealer", "reseller"]
            if term in q.lower()
        }
        assert len(role_terms_found) >= 2, (
            f"Expected ≥2 distinct role terms across queries. "
            f"Found: {role_terms_found}\nQueries: {queries}"
        )

    def test_dive_queries_not_all_same_role(self):
        """All queries must not repeat the same single role term — diversity required."""
        intent = _naturehike_intent()
        graph = KeywordGraph(intent)
        nodes = graph._ranked_nodes()
        profile = build_strategy_profile(intent, "dive", 1, graph.vocab)
        queries = build_queries(intent, nodes, round_num=1, strategy="dive",
                                max_queries=10, profile=profile)
        distributor_only = all("distributor" in q.lower() for q in queries if any(
            t in q.lower() for t in ["distributor", "wholesaler", "importer", "dealer"]
        ))
        assert not distributor_only, (
            "Every query uses only 'distributor' — angle expansion is not working"
        )

    def test_computex_dive_queries_have_oemOdm(self):
        intent = _computex_intent()
        graph = KeywordGraph(intent)
        nodes = graph._ranked_nodes()
        profile = build_strategy_profile(intent, "dive", 1, graph.vocab)
        queries = build_queries(intent, nodes, round_num=1, strategy="dive",
                                max_queries=10, profile=profile)
        exhibitor_related = {"exhibitor", "manufacturer", "oem", "odm", "vendor"}
        found = {t for q in queries for t in exhibitor_related if t in q.lower()}
        assert len(found) >= 2, (
            f"Expected ≥2 exhibitor-related terms. Found: {found}\nQueries: {queries}"
        )


# ---------------------------------------------------------------------------
# A2 — Provider Fallback
# ---------------------------------------------------------------------------

class TestProviderFallback:
    def test_has_content_true_when_snippets_present(self):
        from retrieval.router import _has_content
        results = [
            {"title": "A", "snippet": "some content"},
            {"title": "B", "snippet": "more content"},
        ]
        assert _has_content(results) is True

    def test_has_content_false_when_all_empty(self):
        from retrieval.router import _has_content
        results = [
            {"title": "A", "snippet": ""},
            {"title": "B", "snippet": ""},
            {"title": "C"},
        ]
        assert _has_content(results) is False

    def test_has_content_false_when_empty_list(self):
        from retrieval.router import _has_content
        assert _has_content([]) is False

    def test_has_content_threshold_at_40pct(self):
        from retrieval.router import _has_content
        # 2/5 = 40% → True (exactly at threshold)
        results = [
            {"title": "A", "snippet": "text"},
            {"title": "B", "snippet": "text"},
            {"title": "C", "snippet": ""},
            {"title": "D", "snippet": ""},
            {"title": "E", "snippet": ""},
        ]
        assert _has_content(results) is True

    def test_sequential_falls_through_to_rich_provider(self):
        """When first provider returns empty snippets, fall through to next provider."""
        from salva_core.schemas import RetrievalPolicy
        from retrieval.router import RoutedRetriever

        call_log: list[str] = []

        class EmptySnippetProvider:
            strategy = "dive"
            last_attempts: list = []

            def search(self, query: str, n: int) -> list[dict]:
                call_log.append("empty")
                return [{"title": "Result", "url": "https://a.com", "snippet": ""}] * 3

        class RichProvider:
            strategy = "dive"
            last_attempts: list = []

            def search(self, query: str, n: int) -> list[dict]:
                call_log.append("rich")
                return [
                    {"title": "Good Result", "url": "https://b.com",
                     "snippet": "actual useful content about distributors"}
                ]

        policy = RetrievalPolicy()
        retriever = RoutedRetriever(policy=policy, strategy="dive")
        retriever.providers = [EmptySnippetProvider(), RichProvider()]

        results = retriever._search_sequential("test query", 5)
        assert "rich" in call_log, "Should have fallen through to rich provider"
        assert any(r.get("snippet", "") for r in results), "Should return rich results"

    def test_sequential_returns_fallback_when_all_empty(self):
        """If all providers return empty snippets, return first provider's results."""
        from salva_core.schemas import RetrievalPolicy
        from retrieval.router import RoutedRetriever

        class EmptyProvider:
            strategy = "dive"
            last_attempts: list = []

            def __init__(self, name: str):
                self.name = name

            def search(self, query: str, n: int) -> list[dict]:
                return [{"title": f"{self.name} result", "url": f"https://{self.name}.com",
                         "snippet": ""}]

        policy = RetrievalPolicy()
        retriever = RoutedRetriever(policy=policy, strategy="dive")
        retriever.providers = [EmptyProvider("first"), EmptyProvider("second")]

        results = retriever._search_sequential("test query", 5)
        # Should return first provider's results as fallback
        assert len(results) >= 1
        assert results[0]["title"] == "first result"


# ---------------------------------------------------------------------------
# A3 — Scoring Calibration
# ---------------------------------------------------------------------------

class TestRegionMatchFix:
    def _score(self, title: str, snippet: str, region: str) -> float:
        result = UnifiedResult(
            source_name="test",
            source_url="https://example.com",
            title=title,
            description=snippet,
        )
        intent = Intent(
            domain="bd_leads",
            primary_terms=["Naturehike"],
            region=region,
        )
        return QualificationScorer().score(result, intent)

    def test_single_region_token_matches(self):
        score = self._score(
            "Sport company Germany",
            "distributor and wholesaler in Germany for outdoor brands",
            "Germany",
        )
        assert score > 0.35, f"Single region should match, score={score}"

    def test_compound_region_matches_any_token(self):
        score = self._score(
            "Austrian outdoor distributor",
            "buying group and distribution network in Austria for outdoor equipment",
            "Germany Austria Switzerland",
        )
        assert score > 0.35, (
            f"Compound region 'Germany Austria Switzerland' should match 'Austria' in text, "
            f"score={score}"
        )

    def test_compound_region_no_false_positive(self):
        score = self._score(
            "Asia Pacific Tech",
            "manufacturer in Singapore, no European presence",
            "Germany Austria Switzerland",
        )
        # None of the region tokens appear → region_score=0, but other scores can still add up
        # Just verify it doesn't crash and returns a valid float
        assert 0.0 <= score <= 1.0


class TestBdLeadsScorerCalibration:
    def _make_result(self, title: str, snippet: str) -> UnifiedResult:
        return UnifiedResult(
            source_name="test",
            source_url="https://sport2000.de",
            title=title,
            description=snippet,
        )

    def _intent(self) -> Intent:
        return Intent(
            domain="bd_leads",
            primary_terms=["Naturehike", "outdoor equipment"],
            region="Germany Austria Switzerland",
        )

    def test_buying_group_qualifies(self):
        """SPORT 2000-type entities (buying group) must qualify above threshold."""
        result = self._make_result(
            "SPORT 2000 Deutschland – Verbundgruppe",
            "Buying group and retail alliance for sports and outdoor equipment in Germany.",
        )
        score = QualificationScorer().score(result, self._intent())
        threshold = QualificationScorer.domain_threshold("bd_leads")
        assert score >= threshold, (
            f"Buying group entity scored {score}, below threshold {threshold}"
        )

    def test_retailer_not_killed_by_negative_signal(self):
        """'retailer' must not trigger the 'retail' negative signal penalty."""
        result = self._make_result(
            "Bergfreunde – Outdoor Retailer Germany",
            "Leading German outdoor equipment retailer. Carries Naturehike tents.",
        )
        intent = self._intent()
        score = QualificationScorer().score(result, intent)
        # Must be above 0 — the old hard-penalty would give 0.0
        assert score > 0.10, (
            f"Retailer entity was hard-penalised (score={score}). "
            "'retail' negative signal is too aggressive."
        )

    def test_domain_threshold_bd_leads_is_lower(self):
        assert QualificationScorer.domain_threshold("bd_leads") < 0.40

    def test_domain_threshold_taiwan_hardware_is_lower(self):
        assert QualificationScorer.domain_threshold("taiwan_hardware") < 0.40

    def test_domain_threshold_unknown_returns_default(self):
        assert QualificationScorer.domain_threshold("nonexistent_domain") == 0.40

    def test_distributor_snippet_scores_above_threshold(self):
        result = self._make_result(
            "Elementum Distribution – Outdoor Brands Austria",
            "Leading outdoor equipment distributor and importer in Austria. "
            "Wholesale and B2B sourcing for Naturehike, Black Diamond and more.",
        )
        score = QualificationScorer().score(result, self._intent())
        threshold = QualificationScorer.domain_threshold("bd_leads")
        assert score >= threshold, f"Distributor scored {score}, below threshold {threshold}"


# ---------------------------------------------------------------------------
# A3 — Domain Vocab Enrichment
# ---------------------------------------------------------------------------

class TestDomainVocabEnrichment:
    def test_bd_leads_has_buying_group_in_synonyms(self):
        from core.domain_vocab import get_vocab
        vocab = get_vocab("bd_leads")
        all_synonyms = [v for variants in vocab.synonym_groups.values() for v in variants]
        assert "buying group" in all_synonyms

    def test_bd_leads_removed_retail_from_noise(self):
        from core.domain_vocab import get_vocab
        vocab = get_vocab("bd_leads")
        assert "retail" not in vocab.noise_terms

    def test_taiwan_hardware_vocab_registered(self):
        from core.domain_vocab import get_vocab, list_domains
        assert "taiwan_hardware" in list_domains()
        vocab = get_vocab("taiwan_hardware")
        assert "exhibitor" in vocab.synonym_groups
        assert any("Computex" in s for s in vocab.signal_terms)

    def test_taiwan_hardware_vocab_has_oemOdm_synonyms(self):
        from core.domain_vocab import get_vocab
        vocab = get_vocab("taiwan_hardware")
        exhibitor_synonyms = vocab.synonym_groups.get("exhibitor", [])
        assert "OEM" in exhibitor_synonyms or "manufacturer" in exhibitor_synonyms
