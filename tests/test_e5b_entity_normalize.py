"""E5b closure — normalize_alias + resolve_entity_normalized.

E5b showed Jina embedding alone fails for cross-script resolution (F1=0.31).
E16 confirmed the static gazetteer approach works (11/11 PASS).

These tests validate the deterministic normalization bridge that handles:
  - Legal suffix variation: "TSMC Ltd" → same canonical as "TSMC"
  - NFKC form differences: fullwidth/halfwidth chars
  - Case insensitivity
  - Exact hit takes priority over normalized hit
"""
from __future__ import annotations

import pytest

from salva_core.persistence.db import ensure_db
from salva_core.persistence.hold import (
    add_entity_alias,
    normalize_alias,
    resolve_canonical_id,
    resolve_entity_normalized,
    upsert_canonical_entity,
)


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test_e5b_normalize.db")
    ensure_db(path)
    return path


@pytest.fixture
def seeded_db(db_path):
    upsert_canonical_entity(
        canonical_id="tsmc:canonical",
        entity_type="company",
        primary_label="TSMC",
        jurisdiction="TW",
        path=db_path,
    )
    for alias, script in [
        ("TSMC", "en"),
        ("台積電", "zh-TW"),
        ("Taiwan Semiconductor Manufacturing Company", "en"),
        ("2330.TW", "ticker"),
    ]:
        add_entity_alias("tsmc:canonical", alias, script=script, path=db_path)
    return db_path


# ---------------------------------------------------------------------------
# normalize_alias unit tests
# ---------------------------------------------------------------------------

def test_normalize_strips_legal_suffixes() -> None:
    assert normalize_alias("TSMC Ltd") == "tsmc"
    assert normalize_alias("GIGABYTE Technology Co., Ltd.") == "gigabyte technology"
    assert normalize_alias("Foxconn") == "foxconn"


def test_normalize_handles_chinese_legal_suffixes() -> None:
    result = normalize_alias("台灣積體電路製造股份有限公司")
    assert "股份有限公司" not in result
    assert "台灣積體電路製造" in result or "製造" in result


def test_normalize_lowercases() -> None:
    assert normalize_alias("TSMC") == "tsmc"


def test_normalize_nfkc() -> None:
    # fullwidth A (U+FF21) normalizes to A
    assert normalize_alias("ＴＳＭＣ") == "tsmc"


# ---------------------------------------------------------------------------
# resolve_entity_normalized integration tests
# ---------------------------------------------------------------------------

def test_exact_match_takes_priority(seeded_db) -> None:
    result = resolve_entity_normalized("TSMC", path=seeded_db)
    assert result == "tsmc:canonical"


def test_normalized_match_on_legal_suffix_variant(seeded_db) -> None:
    result = resolve_entity_normalized("TSMC Ltd", path=seeded_db)
    assert result == "tsmc:canonical"


def test_normalized_match_case_insensitive(seeded_db) -> None:
    result = resolve_entity_normalized("tsmc", path=seeded_db)
    assert result == "tsmc:canonical"


def test_no_match_returns_none(seeded_db) -> None:
    result = resolve_entity_normalized("Alibaba", path=seeded_db)
    assert result is None


def test_exact_match_beats_normalized_for_ambiguous_suffix(seeded_db) -> None:
    # If "TSMC" is in aliases, exact match fires before normalized scan
    result1 = resolve_canonical_id("TSMC", path=seeded_db)
    result2 = resolve_entity_normalized("TSMC", path=seeded_db)
    assert result1 == result2 == "tsmc:canonical"


def test_distinct_entities_do_not_collide(seeded_db) -> None:
    upsert_canonical_entity(
        canonical_id="samsung:canonical",
        entity_type="company",
        primary_label="Samsung",
        jurisdiction="KR",
        path=seeded_db,
    )
    add_entity_alias("samsung:canonical", "Samsung Electronics", script="en", path=seeded_db)

    tsmc = resolve_entity_normalized("TSMC", path=seeded_db)
    samsung = resolve_entity_normalized("Samsung Electronics", path=seeded_db)

    assert tsmc == "tsmc:canonical"
    assert samsung == "samsung:canonical"
    assert tsmc != samsung
