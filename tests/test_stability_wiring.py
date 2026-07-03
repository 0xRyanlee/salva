"""Regression coverage for stability-gating wiring across three layers:
processing/scorer.py (composite formula), core/controller.py (scoring_context
plumbing into telemetry.metadata), salva_core/service.py (compute-once +
default-off gate). No end-to-end retrieval -- these test the wiring, not
compute_stability_signals() itself (see tests/test_stability.py) or a live
discovery run.
"""
from __future__ import annotations

from types import SimpleNamespace

from core.controller import SalvaController
from core.types import Intent, UnifiedResult
from processing.scorer import QualificationScorer, ScorerConfig


def _result(has_snippet: bool = True) -> UnifiedResult:
    return UnifiedResult(
        source_name="Acme Hardware Co",
        source_url="acme.example.com",
        title="Acme Hardware Co",
        description="AI hardware manufacturer" if has_snippet else "",
    )


def _intent() -> Intent:
    return Intent(domain="companies", primary_terms=["AI hardware"])


class TestScorerStabilityTerm:
    def test_absent_stability_score_leaves_composite_unchanged(self):
        cfg = ScorerConfig(w_stability=0.3)  # non-zero weight, but no value provided
        scorer = QualificationScorer(cfg)
        baseline = QualificationScorer(ScorerConfig()).score(_result(), _intent(), context={})
        with_weight_no_value = scorer.score(_result(), _intent(), context={})
        assert with_weight_no_value == baseline

    def test_zero_w_stability_ignores_stability_score_in_context(self):
        scorer = QualificationScorer(ScorerConfig())  # w_stability=0.0 default
        baseline = scorer.score(_result(), _intent(), context={})
        with_score_but_no_weight = scorer.score(
            _result(), _intent(), context={"stability_score": 0.9}
        )
        assert with_score_but_no_weight == baseline

    def test_context_w_stability_and_score_move_the_composite(self):
        scorer = QualificationScorer(ScorerConfig())
        baseline = scorer.score(_result(), _intent(), context={})
        boosted = scorer.score(
            _result(), _intent(),
            context={"w_stability": 0.5, "stability_score": 1.0},
        )
        assert boosted != baseline
        assert boosted > baseline  # a perfect (1.0) stability score should not lower it

    def test_context_w_stability_override_participates_in_renormalization(self):
        adjusted = QualificationScorer._apply_context(
            ScorerConfig(), {"w_stability": 0.2}
        )
        total = (
            adjusted.w_content + adjusted.w_contact + adjusted.w_signal
            + adjusted.w_region + adjusted.w_source + adjusted.w_recency
            + adjusted.w_stability
        )
        assert abs(total - 1.0) < 1e-9
        assert adjusted.w_stability > 0.0


class TestControllerScoringContext:
    def test_defaults_to_empty_dict(self):
        ctrl = SalvaController(
            intent=_intent(), retrievers={}, extractor=None, deduplicator=None,
            scorer=QualificationScorer(),
        )
        assert ctrl.scoring_context == {}

    def test_stores_provided_scoring_context(self):
        ctrl = SalvaController(
            intent=_intent(), retrievers={}, extractor=None, deduplicator=None,
            scorer=QualificationScorer(),
            scoring_context={"w_stability": 0.15, "stability_score": 0.7},
        )
        assert ctrl.scoring_context == {"w_stability": 0.15, "stability_score": 0.7}


class TestBuildStabilityScoringContext:
    def test_real_default_discovery_request_returns_empty_dict(self):
        """The actual production call site: DiscoveryRequest has no `stability`
        field yet (added by a follow-up card), so getattr() always returns
        None today -- this must be {} for every real request right now."""
        from salva_core.schemas import DiscoveryIntent, DiscoveryRequest
        from salva_core.service import _build_stability_scoring_context

        payload = DiscoveryRequest(
            objective="find_companies",
            intent=DiscoveryIntent(market="US", industry="AI"),
        )
        assert _build_stability_scoring_context(payload, "companies") == {}

    def test_disabled_policy_returns_empty_dict(self):
        from salva_core.service import _build_stability_scoring_context

        payload = SimpleNamespace(stability=SimpleNamespace(enabled=False))
        assert _build_stability_scoring_context(payload, "companies") == {}

    def test_enabled_policy_with_insufficient_history_returns_empty_dict(
        self, tmp_path, monkeypatch
    ):
        from salva_core.service import _build_stability_scoring_context

        monkeypatch.setattr(
            "salva_core.persistence.db.DEFAULT_DB_PATH", str(tmp_path / "salva_test.db")
        )
        payload = SimpleNamespace(
            stability=SimpleNamespace(enabled=True, min_history=3, penalty_strength=0.15),
            execution=SimpleNamespace(project_id=None),
        )
        # No query_family_memory rows seeded for this domain -> None from
        # compute_stability_signals() -> {} here, not an exception.
        assert _build_stability_scoring_context(payload, "nonexistent-domain") == {}

    def test_enabled_policy_with_sufficient_history_returns_weight_and_score(
        self, tmp_path, monkeypatch
    ):
        import json

        from salva_core.persistence.db import get_conn
        from salva_core.service import _build_stability_scoring_context

        db_path = str(tmp_path / "salva_test.db")
        # _build_stability_scoring_context resolves the path via
        # get_db_path_for_project(payload.execution.project_id), which
        # returns DEFAULT_DB_PATH for project_id=None -- patch that module
        # global (read fresh inside the function body, not a baked-in
        # default parameter) so it points at this test's isolated DB.
        monkeypatch.setattr("salva_core.persistence.db.DEFAULT_DB_PATH", db_path)
        with get_conn(db_path) as conn:
            for i in range(3):
                conn.execute(
                    """
                    INSERT INTO query_family_memory (
                        memory_id, run_id, memory_status, domain, objective,
                        output_profile, round_num, strategy, query, query_signature,
                        source_nodes_json, content_nodes_json, content_weights_json,
                        source_hints_json, notes_json, raw_total, qualified_total,
                        avg_score, success_score, created_at
                    ) VALUES (?, ?, 'legacy', 'companies', 'find_companies',
                              'company_profile', 1, 'dive', ?, ?, '[]', ?, '{}',
                              '[]', '[]', 5, 3, 0.6, 0.7, ?)
                    """,
                    (
                        f"m{i}", f"run-{i}", f"query {i}", f"sig-{i}",
                        json.dumps(["ai", "hardware"]), f"2026-01-0{i + 1}T00:00:00",
                    ),
                )

        payload = SimpleNamespace(
            stability=SimpleNamespace(enabled=True, min_history=3, penalty_strength=0.15),
            execution=SimpleNamespace(project_id=None),
        )
        result = _build_stability_scoring_context(payload, "companies")

        assert result["w_stability"] == 0.15
        assert 0.0 <= result["stability_score"] <= 1.0
