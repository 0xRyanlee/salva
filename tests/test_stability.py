"""Unit tests for salva_core/stability.py -- pure functions, no wiring.

Inserts controlled rows directly into query_family_memory (SQLite FK
enforcement is off by default in this codebase, so no parent
discovery_runs row is needed) rather than routing through the full
discovery pipeline, so drift/volatility inputs can be pinned exactly.
"""
from __future__ import annotations

import json

from salva_core.persistence.db import get_conn
from salva_core.stability import compute_stability_signals


def _insert_query_family_row(
    db_path: str,
    *,
    memory_id: str,
    domain: str,
    content_nodes: list[str],
    success_score: float,
    created_at: str,
) -> None:
    with get_conn(db_path) as conn:
        conn.execute(
            """
            INSERT INTO query_family_memory (
                memory_id, run_id, memory_status, domain, objective,
                output_profile, round_num, strategy, query, query_signature,
                source_nodes_json, content_nodes_json, content_weights_json,
                source_hints_json, notes_json, raw_total, qualified_total,
                avg_score, success_score, created_at
            ) VALUES (?, ?, 'legacy', ?, 'find_companies', 'company_profile',
                      1, 'dive', ?, ?, '[]', ?, '{}', '[]', '[]', 5, 3, 0.6, ?, ?)
            """,
            (
                memory_id, f"run-{memory_id}", domain, f"query {memory_id}",
                f"sig-{memory_id}", json.dumps(content_nodes), success_score, created_at,
            ),
        )


class TestComputeStabilitySignals:
    def test_returns_none_when_history_below_min_history(self, tmp_path):
        db_path = str(tmp_path / "salva_test.db")
        _insert_query_family_row(
            db_path, memory_id="m1", domain="companies",
            content_nodes=["ai", "hardware"], success_score=0.7,
            created_at="2026-01-01T00:00:00",
        )
        _insert_query_family_row(
            db_path, memory_id="m2", domain="companies",
            content_nodes=["ai", "hardware"], success_score=0.7,
            created_at="2026-01-02T00:00:00",
        )
        # Only 2 rows, default min_history=3 -- not enough data.
        assert compute_stability_signals("companies", path=db_path) is None

    def test_identical_history_yields_near_zero_drift_and_volatility(self, tmp_path):
        db_path = str(tmp_path / "salva_test.db")
        for i in range(4):
            _insert_query_family_row(
                db_path, memory_id=f"stable-{i}", domain="companies",
                content_nodes=["ai", "hardware", "company"], success_score=0.7,
                created_at=f"2026-01-0{i + 1}T00:00:00",
            )

        signals = compute_stability_signals("companies", min_history=3, path=db_path)

        assert signals is not None
        assert signals["drift"] == 0.0
        assert signals["volatility"] == 0.0

    def test_diverging_history_yields_clearly_higher_drift_and_volatility(self, tmp_path):
        db_path = str(tmp_path / "salva_test.db")
        term_sets = [
            ["ai", "hardware", "company"],
            ["vegetable", "farm", "organic"],
            ["cloud", "infra", "startup"],
            ["legal", "tech", "saas"],
        ]
        scores = [0.9, 0.1, 0.8, 0.2]
        for i, (terms, score) in enumerate(zip(term_sets, scores, strict=True)):
            _insert_query_family_row(
                db_path, memory_id=f"volatile-{i}", domain="companies",
                content_nodes=terms, success_score=score,
                created_at=f"2026-01-0{i + 1}T00:00:00",
            )

        signals = compute_stability_signals("companies", min_history=3, path=db_path)

        assert signals is not None
        assert signals["drift"] > 0.8  # near-disjoint term sets each step
        assert signals["volatility"] > 0.2  # scores swing 0.1 <-> 0.9

    def test_domain_filter_ignores_other_domains(self, tmp_path):
        db_path = str(tmp_path / "salva_test.db")
        for i in range(3):
            _insert_query_family_row(
                db_path, memory_id=f"companies-{i}", domain="companies",
                content_nodes=["ai"], success_score=0.5,
                created_at=f"2026-01-0{i + 1}T00:00:00",
            )
        for i in range(3):
            _insert_query_family_row(
                db_path, memory_id=f"events-{i}", domain="events",
                content_nodes=["conference"], success_score=0.9,
                created_at=f"2026-01-0{i + 1}T00:00:00",
            )

        signals = compute_stability_signals("events", min_history=3, path=db_path)
        assert signals is not None
        # Only the 3 "events" rows should be counted -- if "companies" rows
        # leaked in, volatility would be non-zero (0.5 vs 0.9 mixed).
        assert signals["volatility"] == 0.0

    def test_domain_normalization_matches_stored_domain_case_insensitively(self, tmp_path):
        db_path = str(tmp_path / "salva_test.db")
        for i in range(3):
            _insert_query_family_row(
                db_path, memory_id=f"norm-{i}", domain="Companies",
                content_nodes=["ai"], success_score=0.5,
                created_at=f"2026-01-0{i + 1}T00:00:00",
            )
        assert compute_stability_signals("companies", min_history=3, path=db_path) is not None
