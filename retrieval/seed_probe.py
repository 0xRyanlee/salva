"""Seed URL probe — classify whether a URL is safely fetchable before seeding.

Returns a SeedProbeResult indicating whether the URL is:
  static_ok         — static HTML, content extracted successfully
  js_required       — Obscura renders more text than http_get (JS inflates content)
  ajax_suspected    — Obscura renders page but eval returns near-empty content
  blocked_or_unusable — both http_get and Obscura fail or return trivially short content
  unknown           — probe failed with an exception

Used by controller._bootstrap_seed_urls() to annotate seed URL quality and skip
URLs that will waste budget on empty/blocked content.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

from retrieval.http import http_get
from salva_core.schemas import RetrievalPolicy

logger = logging.getLogger("salva.retrieval.seed_probe")

_MIN_STATIC_CHARS = 200   # below this → likely WAF block or empty page
_JS_INFLATION_RATIO = 2.0 # obscura_len / static_len > this → JS-heavy


class SeedProbeStatus(str, Enum):
    STATIC_OK = "static_ok"
    JS_REQUIRED = "js_required"
    AJAX_SUSPECTED = "ajax_suspected"
    BLOCKED_OR_UNUSABLE = "blocked_or_unusable"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class SeedProbeResult:
    url: str
    status: SeedProbeStatus
    static_len: int = 0
    obscura_len: int = 0
    expected_terms_hit: int = 0

    @property
    def is_usable(self) -> bool:
        return self.status in (SeedProbeStatus.STATIC_OK, SeedProbeStatus.JS_REQUIRED)


def probe_seed_url(
    url: str,
    policy: RetrievalPolicy,
    expected_terms: list[str] | None = None,
) -> SeedProbeResult:
    """
    Probe `url` to determine fetch strategy. Does not raise.

    Args:
        url: URL to probe.
        policy: RetrievalPolicy (timeout, obscura settings).
        expected_terms: Optional list of strings to look for in fetched content;
                        hit count is reported in the result.
    """
    expected = [t.lower() for t in (expected_terms or [])]

    # --- Static fetch ---
    static_text = ""
    try:
        raw = http_get(url, headers={"Accept": "text/html"}, timeout=policy.request_timeout)
        static_text = raw.decode("utf-8", errors="replace")
    except Exception as exc:
        logger.debug("seed_probe: static fetch %s failed: %s", url, exc)

    static_len = len(static_text)

    # --- Obscura fetch (optional) ---
    from retrieval.seed_fetcher import _obscura_binary, _obscura_fetch_text
    obscura_text = ""
    if _obscura_binary():
        obscura_text = _obscura_fetch_text(url, timeout_ms=int(policy.request_timeout * 1000)) or ""
    obscura_len = len(obscura_text)

    # --- Term hit count ---
    check_text = (obscura_text or static_text).lower()
    terms_hit = sum(1 for t in expected if t in check_text)

    # --- Classification ---
    if static_len == 0 and obscura_len == 0:
        status = SeedProbeStatus.BLOCKED_OR_UNUSABLE
    elif static_len < _MIN_STATIC_CHARS and obscura_len < _MIN_STATIC_CHARS:
        status = SeedProbeStatus.BLOCKED_OR_UNUSABLE
    elif obscura_len > 0 and static_len > 0 and (obscura_len / static_len) > _JS_INFLATION_RATIO:
        # Obscura renders much more — JS is doing real work
        if obscura_len < _MIN_STATIC_CHARS:
            status = SeedProbeStatus.AJAX_SUSPECTED
        else:
            status = SeedProbeStatus.JS_REQUIRED
    elif static_len >= _MIN_STATIC_CHARS:
        status = SeedProbeStatus.STATIC_OK
    elif obscura_len >= _MIN_STATIC_CHARS:
        status = SeedProbeStatus.JS_REQUIRED
    else:
        status = SeedProbeStatus.UNKNOWN

    logger.debug(
        "seed_probe: %s → %s (static=%d obscura=%d terms_hit=%d/%d)",
        url, status.value, static_len, obscura_len, terms_hit, len(expected),
    )
    return SeedProbeResult(
        url=url,
        status=status,
        static_len=static_len,
        obscura_len=obscura_len,
        expected_terms_hit=terms_hit,
    )
