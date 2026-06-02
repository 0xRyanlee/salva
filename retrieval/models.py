from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RetrievalAttempt:
    provider: str
    base_url: str
    mode: str
    result_count: int
    succeeded: bool
    error: str | None = None
    format_used: str | None = None
