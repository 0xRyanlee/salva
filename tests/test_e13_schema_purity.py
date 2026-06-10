"""E13 — Objective → Schema purity.

VP13: find_companies / find_leads entities must not carry event-schema defaults
(timezone="Asia/Taipei", currency="TWD", price_amount=0.0).  After the fix,
these fields default to None and _build_event_details() returns None for
non-event results.
"""
from __future__ import annotations

from core.types import UnifiedResult
from salva_core.legacy import _build_event_details, legacy_result_to_entity


def _company_result(**kwargs) -> UnifiedResult:
    return UnifiedResult(
        source_name="ddg_html",
        source_url="https://example-distributor.de/",
        title="Example GmbH – outdoor equipment distributor",
        **kwargs,
    )


class TestUnifiedResultDefaults:
    def test_timezone_defaults_to_none(self):
        r = _company_result()
        assert r.timezone is None

    def test_currency_defaults_to_none(self):
        r = _company_result()
        assert r.currency is None

    def test_price_amount_defaults_to_none(self):
        r = _company_result()
        assert r.price_amount is None


class TestEventDetailsNotInjected:
    def test_company_result_has_no_event_details(self):
        r = _company_result()
        assert _build_event_details(r) is None

    def test_lead_result_with_domain_has_no_event_details(self):
        r = _company_result(organizer_domain="example-distributor.de")
        assert _build_event_details(r) is None

    def test_event_result_does_have_event_details(self):
        from datetime import datetime
        r = _company_result(starts_at=datetime(2026, 6, 1))
        assert _build_event_details(r) is not None


class TestLegacyEntityOutputClean:
    def test_entity_event_field_is_none_for_company_result(self):
        r = _company_result(organizer_domain="example-distributor.de")
        r.qualified = True
        r.relevance_score = 0.75
        entity = legacy_result_to_entity(r, market="Germany")
        # event field must be None — no event pollution in company output
        assert entity.event is None

    def test_entity_event_field_present_for_event_result(self):
        from datetime import datetime
        r = _company_result(starts_at=datetime(2026, 9, 1))
        r.qualified = True
        r.relevance_score = 0.75
        entity = legacy_result_to_entity(r, market="Germany")
        assert entity.event is not None
