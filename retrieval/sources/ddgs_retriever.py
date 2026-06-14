"""
DDGS retrieval source using the `ddgs` library (primp Rust TLS impersonation).

Replaces the brittle urllib-based DDGHTMLRetriever with a library that bypasses
bot-detection via JA3/TLS fingerprint spoofing. Falls back gracefully when ddgs
is not installed (importable-check at runtime, not import-time).

Environment:
  DDGS_PROXY  — optional SOCKS5/HTTP proxy (e.g. socks5://127.0.0.1:1080)
  DDGS_BACKEND — comma-separated engine list: auto, google, bing, ddg, brave, yandex...
                 default "auto" (let ddgs pick the best available)
"""
from __future__ import annotations

import logging
import os
from typing import Any

from retrieval.models import RetrievalAttempt
from salva_core.schemas import RetrievalPolicy

logger = logging.getLogger("salva.retrieval.ddgs")

_DDGS_AVAILABLE: bool | None = None

try:
    from ddgs import DDGS
    _DDGS_AVAILABLE = True
except ImportError:
    DDGS = None  # type: ignore[assignment,misc]
    _DDGS_AVAILABLE = False


def _is_ddgs_available() -> bool:
    return bool(_DDGS_AVAILABLE)


class DDGSRetriever:
    strategy = "radar"

    def __init__(self, policy: RetrievalPolicy):
        self.policy = policy
        self.last_attempts: list[RetrievalAttempt] = []
        self._proxy = os.getenv("DDGS_PROXY", "").strip() or None
        raw_backend = os.getenv("DDGS_BACKEND", "auto").strip()
        self._backend = raw_backend if raw_backend else "auto"

    def search(self, query: str, n: int = 10) -> list[dict[str, Any]]:
        self.last_attempts = []
        if not _is_ddgs_available():
            return []

        try:
            results = self._run_search(query, n)
            self.last_attempts.append(
                RetrievalAttempt(
                    provider="ddgs",
                    base_url="ddgs://search",
                    mode=self.policy.mode,
                    result_count=len(results),
                    succeeded=bool(results),
                    format_used="api",
                )
            )
            return results
        except Exception as exc:
            logger.debug("DDGS search failed: %s", exc)
            self.last_attempts.append(
                RetrievalAttempt(
                    provider="ddgs",
                    base_url="ddgs://search",
                    mode=self.policy.mode,
                    result_count=0,
                    succeeded=False,
                    error=str(exc),
                    format_used="api",
                )
            )
            return []

    def _run_search(self, query: str, n: int) -> list[dict[str, Any]]:
        kwargs: dict[str, Any] = {}
        if self._proxy:
            kwargs["proxy"] = self._proxy

        region = self.policy.region_hint or "wt-wt"

        with DDGS(**kwargs) as ddgs:
            raw = ddgs.text(
                query,
                region=region,
                max_results=n,
                backend=self._backend,
            )

        results: list[dict[str, Any]] = []
        for item in raw or []:
            url = item.get("href") or item.get("url", "")
            if not url:
                continue
            results.append(
                {
                    "title": item.get("title", ""),
                    "url": url,
                    "snippet": item.get("body", ""),
                    "engine": f"ddgs/{self._backend}",
                    "retrieval_instance": "ddgs",
                }
            )
        return results
