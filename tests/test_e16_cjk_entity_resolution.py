"""E16 — Cross-language entity resolution: Computex Taiwan hardware companies.

VP16: When two results for the same company arrive with different scripts
(ZH: 技嘉科技 / EN: GIGABYTE Technology), the Hold C2 gazetteer must:
  1. Resolve both surface forms to the same canonical_id.
  2. Produce aliases for both scripts.
  3. Not merge distinct companies (GIGABYTE ≠ MSI).

This validates that the static gazetteer approach (Hold C2) covers the
cross-script gap proven un-bridgeable by Jina v5 in E5b.
"""
from __future__ import annotations

import pytest

from salva_core.persistence.hold import (
    add_entity_alias,
    get_aliases_for_canonical,
    resolve_canonical_id,
    upsert_canonical_entity,
)


@pytest.fixture
def db_path(tmp_path):
    """Isolated DB with full Salva schema for Hold C2 tests."""
    from salva_core.persistence.db import ensure_db
    path = str(tmp_path / "test_e16.db")
    ensure_db(path)
    return path


# ---------------------------------------------------------------------------
# Computex fixture — top Taiwan hardware exhibitors
# ---------------------------------------------------------------------------

COMPUTEX_GAZETTEER: list[dict] = [
    {
        "canonical_id": "twh:gigabyte",
        "canonical_label": "GIGABYTE Technology Co., Ltd.",
        "entity_type": "company",
        "jurisdiction": "TW",
        "aliases": [
            ("技嘉科技", "zh-TW"),
            ("技嘉科技股份有限公司", "zh-TW"),
            ("技嘉", "zh-TW"),
            ("GIGABYTE", "en"),
            ("Gigabyte Technology", "en"),
            ("2376.TW", "ticker"),
        ],
    },
    {
        "canonical_id": "twh:msi",
        "canonical_label": "Micro-Star International Co., Ltd.",
        "entity_type": "company",
        "jurisdiction": "TW",
        "aliases": [
            ("微星科技", "zh-TW"),
            ("微星科技股份有限公司", "zh-TW"),
            ("微星", "zh-TW"),
            ("MSI", "en"),
            ("Micro-Star International", "en"),
            ("2377.TW", "ticker"),
        ],
    },
    {
        "canonical_id": "twh:asus",
        "canonical_label": "ASUSTeK Computer Inc.",
        "entity_type": "company",
        "jurisdiction": "TW",
        "aliases": [
            ("華碩電腦", "zh-TW"),
            ("華碩電腦股份有限公司", "zh-TW"),
            ("華碩", "zh-TW"),
            ("ASUS", "en"),
            ("ASUSTeK", "en"),
            ("2357.TW", "ticker"),
        ],
    },
]


def _seed_gazetteer(db_path: str) -> None:
    for entry in COMPUTEX_GAZETTEER:
        upsert_canonical_entity(
            canonical_id=entry["canonical_id"],
            entity_type=entry["entity_type"],
            primary_label=entry["canonical_label"],
            jurisdiction=entry["jurisdiction"],
            path=db_path,
        )
        for surface, locale in entry["aliases"]:
            add_entity_alias(
                canonical_id=entry["canonical_id"],
                alias=surface,
                script=locale,
                source="computex_gazetteer",
                path=db_path,
            )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCrossScriptResolution:
    def test_zh_resolves_to_canonical(self, db_path):
        _seed_gazetteer(db_path)
        cid = resolve_canonical_id("技嘉科技", path=db_path)
        assert cid == "twh:gigabyte", f"ZH surface should resolve to twh:gigabyte, got {cid}"

    def test_en_resolves_to_same_canonical(self, db_path):
        _seed_gazetteer(db_path)
        cid = resolve_canonical_id("GIGABYTE", path=db_path)
        assert cid == "twh:gigabyte", f"EN surface should resolve to twh:gigabyte, got {cid}"

    def test_ticker_resolves_to_canonical(self, db_path):
        _seed_gazetteer(db_path)
        cid = resolve_canonical_id("2376.TW", path=db_path)
        assert cid == "twh:gigabyte", f"Ticker should resolve to twh:gigabyte, got {cid}"

    def test_zh_en_same_canonical_id(self, db_path):
        _seed_gazetteer(db_path)
        zh_cid = resolve_canonical_id("技嘉科技", path=db_path)
        en_cid = resolve_canonical_id("GIGABYTE", path=db_path)
        assert zh_cid == en_cid, (
            f"ZH and EN surface forms must map to same canonical. "
            f"ZH→{zh_cid}, EN→{en_cid}"
        )

    def test_distinct_companies_not_merged(self, db_path):
        _seed_gazetteer(db_path)
        gigabyte_cid = resolve_canonical_id("GIGABYTE", path=db_path)
        msi_cid = resolve_canonical_id("MSI", path=db_path)
        assert gigabyte_cid != msi_cid, "GIGABYTE and MSI must not merge"

    def test_aliases_retrievable_for_canonical(self, db_path):
        _seed_gazetteer(db_path)
        aliases = get_aliases_for_canonical("twh:gigabyte", path=db_path)
        surfaces = [a["alias"] for a in aliases]
        assert "技嘉科技" in surfaces
        assert "GIGABYTE" in surfaces
        assert "2376.TW" in surfaces

    def test_unknown_surface_returns_none(self, db_path):
        _seed_gazetteer(db_path)
        cid = resolve_canonical_id("SomeUnknownCompany XYZ", path=db_path)
        assert cid is None


class TestMultiCompanyGazetteer:
    def test_all_three_companies_resolvable(self, db_path):
        _seed_gazetteer(db_path)
        cases = [
            ("技嘉科技", "twh:gigabyte"),
            ("微星科技", "twh:msi"),
            ("華碩電腦", "twh:asus"),
            ("GIGABYTE", "twh:gigabyte"),
            ("MSI", "twh:msi"),
            ("ASUS", "twh:asus"),
        ]
        for surface, expected_cid in cases:
            cid = resolve_canonical_id(surface, path=db_path)
            assert cid == expected_cid, f"'{surface}' → expected {expected_cid}, got {cid}"

    def test_abbreviation_aliases(self, db_path):
        _seed_gazetteer(db_path)
        assert resolve_canonical_id("技嘉", path=db_path) == "twh:gigabyte"
        assert resolve_canonical_id("微星", path=db_path) == "twh:msi"
        assert resolve_canonical_id("華碩", path=db_path) == "twh:asus"

    def test_no_cross_contamination(self, db_path):
        """MSI aliases must not resolve to GIGABYTE or ASUS canonical."""
        _seed_gazetteer(db_path)
        for msi_alias in ("微星科技", "MSI", "微星", "2377.TW"):
            cid = resolve_canonical_id(msi_alias, path=db_path)
            assert cid == "twh:msi", (
                f"MSI alias '{msi_alias}' resolved to '{cid}', expected 'twh:msi'"
            )
