"""Provider health tracking and circuit breaker for free-first retrieval.

Each provider (identified by a string ID like "ddg", "searxng:https://searx.be",
"marginalia") gets independent health state. The circuit breaker opens after
consecutive_failure_threshold failures and stays open until cooldown_seconds pass.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import ClassVar


class ProviderErrorType(str, Enum):
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    AUTH_ERROR = "auth_error"
    EMPTY_RESULT = "empty_result"
    NETWORK_ERROR = "network_error"
    PARSE_ERROR = "parse_error"
    BLOCKED = "blocked"


# Cooldown seconds per error type (how long to back off before retrying)
ERROR_COOLDOWNS: dict[ProviderErrorType, float] = {
    ProviderErrorType.TIMEOUT:       300.0,   # 5 min
    ProviderErrorType.RATE_LIMIT:    14400.0, # 4 h
    ProviderErrorType.AUTH_ERROR:    86400.0, # 24 h — likely needs config fix
    ProviderErrorType.EMPTY_RESULT:  60.0,    # 1 min
    ProviderErrorType.NETWORK_ERROR: 300.0,   # 5 min
    ProviderErrorType.PARSE_ERROR:   120.0,   # 2 min
    ProviderErrorType.BLOCKED:       14400.0, # 4 h
}


@dataclass
class ProviderHealth:
    provider_id: str
    consecutive_failures: int = 0
    last_success_ts: float = 0.0
    last_failure_ts: float = 0.0
    last_error_type: ProviderErrorType | None = None
    cooldown_until: float = 0.0
    total_successes: int = 0
    total_failures: int = 0

    CONSECUTIVE_FAILURE_THRESHOLD: ClassVar[int] = 3

    def is_usable(self) -> bool:
        if self.cooldown_until and time.monotonic() < self.cooldown_until:
            return False
        return True

    def record_success(self) -> None:
        self.consecutive_failures = 0
        self.last_success_ts = time.monotonic()
        self.cooldown_until = 0.0
        self.total_successes += 1

    def record_failure(self, error_type: ProviderErrorType = ProviderErrorType.NETWORK_ERROR) -> None:
        self.consecutive_failures += 1
        self.last_failure_ts = time.monotonic()
        self.last_error_type = error_type
        self.total_failures += 1
        if self.consecutive_failures >= self.CONSECUTIVE_FAILURE_THRESHOLD:
            cooldown = ERROR_COOLDOWNS.get(error_type, 300.0)
            self.cooldown_until = time.monotonic() + cooldown

    def cooldown_remaining(self) -> float:
        remaining = self.cooldown_until - time.monotonic()
        return max(0.0, remaining)

    def as_dict(self) -> dict:
        return {
            "provider_id": self.provider_id,
            "usable": self.is_usable(),
            "consecutive_failures": self.consecutive_failures,
            "cooldown_remaining_s": round(self.cooldown_remaining(), 1),
            "last_error_type": self.last_error_type.value if self.last_error_type else None,
            "total_successes": self.total_successes,
            "total_failures": self.total_failures,
        }


class ProviderHealthRegistry:
    """In-process registry of provider health states. Shared across retrievers in one run."""

    def __init__(self) -> None:
        self._health: dict[str, ProviderHealth] = {}

    def get(self, provider_id: str) -> ProviderHealth:
        if provider_id not in self._health:
            self._health[provider_id] = ProviderHealth(provider_id=provider_id)
        return self._health[provider_id]

    def is_usable(self, provider_id: str) -> bool:
        return self.get(provider_id).is_usable()

    def record_success(self, provider_id: str) -> None:
        self.get(provider_id).record_success()

    def record_failure(self, provider_id: str, error_type: ProviderErrorType = ProviderErrorType.NETWORK_ERROR) -> None:
        self.get(provider_id).record_failure(error_type)

    def usable_providers(self, provider_ids: list[str]) -> list[str]:
        return [p for p in provider_ids if self.is_usable(p)]

    def status_report(self) -> list[dict]:
        return [h.as_dict() for h in self._health.values()]


# Module-level shared registry (reset per-process)
_DEFAULT_REGISTRY = ProviderHealthRegistry()


def get_health_registry() -> ProviderHealthRegistry:
    return _DEFAULT_REGISTRY
