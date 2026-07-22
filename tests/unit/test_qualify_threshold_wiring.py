"""Regression coverage for salva-p35-scorer-threshold-wiring: domain-calibrated
qualify_threshold (QualificationScorer.domain_threshold()) must actually reach
production requests, not just experiment scripts that call it manually.
"""
from __future__ import annotations

from salva_core.schemas import DiscoveryIntent, DiscoveryRequest
from salva_core.service import _resolve_qualify_threshold


class TestResolveQualifyThreshold:
    def _payload(self, qualify_threshold: float | None = None) -> DiscoveryRequest:
        return DiscoveryRequest(
            objective="find_companies",
            intent=DiscoveryIntent(market="US", industry="AI"),
            qualify_threshold=qualify_threshold,
        )

    def test_unset_uses_domain_default_for_bd_leads(self):
        assert _resolve_qualify_threshold(self._payload(), "bd_leads") == 0.35

    def test_unset_uses_domain_default_for_taiwan_hardware(self):
        assert _resolve_qualify_threshold(self._payload(), "taiwan_hardware") == 0.35

    def test_unset_uses_domain_default_for_partnerships(self):
        assert _resolve_qualify_threshold(self._payload(), "partnerships") == 0.35

    def test_unset_falls_back_to_040_for_unknown_domain(self):
        assert _resolve_qualify_threshold(self._payload(), "nonexistent_domain") == 0.40

    def test_explicit_override_wins_over_domain_default(self):
        # bd_leads' calibrated default is 0.35 -- an explicit 0.9 must still win.
        payload = self._payload(qualify_threshold=0.9)
        assert _resolve_qualify_threshold(payload, "bd_leads") == 0.9

    def test_explicit_value_equal_to_generic_default_still_counts_as_set(self):
        # The whole point of qualify_threshold being float | None: a caller who
        # explicitly passes 0.4 must not be silently reinterpreted as "unset".
        payload = self._payload(qualify_threshold=0.4)
        assert _resolve_qualify_threshold(payload, "bd_leads") == 0.4

    def test_discovery_request_default_is_none_not_040(self):
        """Guards against silently reintroducing the dead-default bug: the
        schema default must be None so _resolve_qualify_threshold can tell
        'not specified' apart from 'specified as 0.4'."""
        payload = self._payload()
        assert payload.qualify_threshold is None
