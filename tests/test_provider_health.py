"""Tests for ProviderHealth + ProviderHealthRegistry (circuit breaker)."""
from __future__ import annotations

import time

import pytest

from retrieval.health import (
    ProviderErrorType,
    ProviderHealth,
    ProviderHealthRegistry,
)


def test_new_provider_is_usable() -> None:
    h = ProviderHealth(provider_id="test")
    assert h.is_usable() is True


def test_record_success_clears_cooldown() -> None:
    h = ProviderHealth(provider_id="test")
    h.cooldown_until = time.monotonic() + 9999
    h.record_success()
    assert h.is_usable() is True
    assert h.cooldown_until == 0.0
    assert h.total_successes == 1


def test_single_failure_does_not_open_circuit() -> None:
    h = ProviderHealth(provider_id="test")
    h.record_failure(ProviderErrorType.RATE_LIMIT)
    # consecutive_failures = 1, threshold = 3 → still usable
    assert h.is_usable() is True
    assert h.consecutive_failures == 1


def test_threshold_failures_open_circuit() -> None:
    h = ProviderHealth(provider_id="test")
    for _ in range(ProviderHealth.CONSECUTIVE_FAILURE_THRESHOLD):
        h.record_failure(ProviderErrorType.RATE_LIMIT)
    assert h.is_usable() is False
    assert h.cooldown_until > time.monotonic()


def test_blocked_error_triggers_long_cooldown() -> None:
    h = ProviderHealth(provider_id="test")
    for _ in range(ProviderHealth.CONSECUTIVE_FAILURE_THRESHOLD):
        h.record_failure(ProviderErrorType.BLOCKED)
    remaining = h.cooldown_remaining()
    # BLOCKED cooldown is 4 hours (14400s); allow small margin
    assert remaining > 14000


def test_timeout_error_shorter_cooldown() -> None:
    h = ProviderHealth(provider_id="test")
    for _ in range(ProviderHealth.CONSECUTIVE_FAILURE_THRESHOLD):
        h.record_failure(ProviderErrorType.TIMEOUT)
    remaining = h.cooldown_remaining()
    assert remaining > 200
    assert remaining < 400  # ~300s cooldown


def test_success_resets_consecutive_failures() -> None:
    h = ProviderHealth(provider_id="test")
    h.record_failure()
    h.record_failure()
    h.record_success()
    assert h.consecutive_failures == 0


def test_as_dict_contains_expected_keys() -> None:
    h = ProviderHealth(provider_id="test_provider")
    d = h.as_dict()
    assert d["provider_id"] == "test_provider"
    assert "usable" in d
    assert "cooldown_remaining_s" in d


# Registry tests

def test_registry_creates_health_on_demand() -> None:
    reg = ProviderHealthRegistry()
    h = reg.get("new_provider")
    assert h.provider_id == "new_provider"
    assert h.is_usable() is True


def test_registry_usable_providers_filters_cooldown() -> None:
    reg = ProviderHealthRegistry()
    reg.record_failure("bad")
    reg.record_failure("bad")
    reg.record_failure("bad")  # threshold reached
    reg.record_success("good")
    usable = reg.usable_providers(["bad", "good", "unknown"])
    assert "bad" not in usable
    assert "good" in usable
    assert "unknown" in usable  # not seen → usable by default


def test_registry_status_report() -> None:
    reg = ProviderHealthRegistry()
    reg.record_success("p1")
    reg.record_failure("p2")
    report = reg.status_report()
    ids = [r["provider_id"] for r in report]
    assert "p1" in ids
    assert "p2" in ids
