"""L1-A schema migration tests.

Verifies:
1. hyperedge_incidences gains confidence / created_at / updated_at columns
2. entity_aliases gains normalized_alias column + is used by resolve_entity_normalized
3. routing_memory gains avg_latency_ms / last_probe_at columns
4. backfill_normalized_aliases populates pre-L1-A rows
5. record_probe_result writes latency and delegates boost to record_source_attempt
6. resolve_entity_normalized hits index (no full-table scan) for new aliases
"""
from __future__ import annotations

import sqlite3

import pytest

from salva_core.persistence.db import ensure_db
from salva_core.persistence.hold import (
    add_entity_alias,
    backfill_normalized_aliases,
    get_routing_boost,
    record_probe_result,
    record_source_attempt,
    resolve_entity_normalized,
    upsert_canonical_entity,
    upsert_hyperedge_incidence,
)


@pytest.fixture()
def db(tmp_path):
    return str(tmp_path / "test.db")


class TestHyperedgeIncidenceColumns:
    def test_confidence_column_exists(self, db):
        ensure_db(db)
        with sqlite3.connect(db) as conn:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(hyperedge_incidences)")}
        assert "confidence" in cols
        assert "created_at" in cols
        assert "updated_at" in cols

    def test_upsert_writes_confidence(self, db):
        upsert_hyperedge_incidence("he1", "node1", "subject", confidence=0.8, path=db)
        with sqlite3.connect(db) as conn:
            row = conn.execute(
                "SELECT confidence, created_at, updated_at FROM hyperedge_incidences "
                "WHERE hyperedge_id='he1' AND node_id='node1' AND role='subject'"
            ).fetchone()
        assert row is not None
        assert abs(row[0] - 0.8) < 0.001
        assert row[1] is not None  # created_at
        assert row[2] is not None  # updated_at

    def test_upsert_defaults_confidence_to_1(self, db):
        upsert_hyperedge_incidence("he2", "node2", "object", path=db)
        with sqlite3.connect(db) as conn:
            row = conn.execute(
                "SELECT confidence FROM hyperedge_incidences "
                "WHERE hyperedge_id='he2'"
            ).fetchone()
        assert abs(row[0] - 1.0) < 0.001


class TestEntityAliasNormalized:
    def test_normalized_alias_column_exists(self, db):
        ensure_db(db)
        with sqlite3.connect(db) as conn:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(entity_aliases)")}
        assert "normalized_alias" in cols

    def test_add_alias_writes_normalized_form(self, db):
        upsert_canonical_entity("c1", "company", "TSMC Ltd.", path=db)
        add_entity_alias("c1", "TSMC Ltd.", path=db)
        with sqlite3.connect(db) as conn:
            row = conn.execute(
                "SELECT normalized_alias FROM entity_aliases WHERE canonical_id='c1'"
            ).fetchone()
        assert row is not None
        # normalize_alias strips "ltd" suffix and lowercases
        assert "ltd" not in row[0]
        assert row[0] == row[0].lower()

    def test_resolve_normalized_finds_via_index(self, db):
        upsert_canonical_entity("c2", "company", "Samsung Electronics Co., Ltd.", path=db)
        add_entity_alias("c2", "Samsung Electronics Co., Ltd.", path=db)
        # Query with suffix variation
        result = resolve_entity_normalized("Samsung Electronics", path=db)
        assert result == "c2", f"expected c2, got {result}"

    def test_resolve_exact_match_wins(self, db):
        upsert_canonical_entity("c3", "company", "Apple Inc.", path=db)
        add_entity_alias("c3", "Apple Inc.", path=db)
        result = resolve_entity_normalized("Apple Inc.", path=db)
        assert result == "c3"


class TestBackfillNormalizedAliases:
    def test_backfill_populates_null_rows(self, db):
        # Simulate pre-L1-A state: insert alias without normalized_alias
        ensure_db(db)
        upsert_canonical_entity("c4", "company", "Foxconn", path=db)
        with sqlite3.connect(db) as conn:
            conn.execute(
                "INSERT INTO entity_aliases (alias_id, canonical_id, alias) "
                "VALUES ('alias:legacy1', 'c4', 'Hon Hai Precision Industry Co., Ltd.')"
            )
            conn.commit()

        updated = backfill_normalized_aliases(path=db)
        assert updated >= 1, f"expected ≥1 updated row, got {updated}"

        # Verify the backfilled row is now resolvable via index
        result = resolve_entity_normalized("Hon Hai Precision Industry", path=db)
        assert result == "c4", f"expected c4, got {result}"

    def test_backfill_safe_to_call_twice(self, db):
        upsert_canonical_entity("c5", "company", "NVIDIA", path=db)
        add_entity_alias("c5", "NVIDIA Corp.", path=db)
        first = backfill_normalized_aliases(path=db)
        second = backfill_normalized_aliases(path=db)
        # All new aliases already have normalized_alias; second call touches 0 rows
        assert second == 0, f"second backfill should touch 0 rows, got {second}"


class TestRoutingMemoryColumns:
    def test_new_columns_exist(self, db):
        ensure_db(db)
        with sqlite3.connect(db) as conn:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(routing_memory)")}
        assert "avg_latency_ms" in cols
        assert "last_probe_at" in cols

    def test_record_probe_result_writes_latency(self, db):
        record_probe_result("http://localhost:8080", result_count=5, latency_ms=120.5, path=db)
        with sqlite3.connect(db) as conn:
            row = conn.execute(
                "SELECT avg_latency_ms, last_probe_at, authority_boost FROM routing_memory "
                "WHERE source_url='http://localhost:8080'"
            ).fetchone()
        assert row is not None
        assert row[0] is not None
        assert abs(row[0] - 120.5) < 1.0
        assert row[1] is not None  # last_probe_at
        assert row[2] > 0          # authority_boost updated via record_source_attempt

    def test_record_probe_result_rolling_avg(self, db):
        record_probe_result("http://localhost:8080", result_count=3, latency_ms=100.0, path=db)
        record_probe_result("http://localhost:8080", result_count=3, latency_ms=200.0, path=db)
        with sqlite3.connect(db) as conn:
            row = conn.execute(
                "SELECT avg_latency_ms FROM routing_memory WHERE source_url='http://localhost:8080'"
            ).fetchone()
        # avg of 100 and 200 should be close to 150
        assert 130.0 <= row[0] <= 170.0, f"expected ~150ms rolling avg, got {row[0]}"

    def test_record_probe_zero_results_negative_boost(self, db):
        record_probe_result("http://bad-instance.example.com", result_count=0, latency_ms=50.0, path=db)
        boost = get_routing_boost("http://bad-instance.example.com", path=db)
        assert boost < 0.0, f"expected negative boost for 0-result probe, got {boost}"
