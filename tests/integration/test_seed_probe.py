"""Tests for SeedProbe — classify seed URLs as static/js-required/blocked."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from retrieval.seed_probe import SeedProbeStatus, probe_seed_url
from salva_core.schemas import RetrievalPolicy


def _policy() -> RetrievalPolicy:
    return RetrievalPolicy()


def _no_obscura():
    import retrieval.seed_fetcher as sf
    return patch.object(sf, "_obscura_binary", return_value=None)


def test_probe_static_ok() -> None:
    """Large static HTML response → STATIC_OK."""
    html = b"<html><body>" + b"Company A " * 100 + b"</body></html>"
    with _no_obscura(), patch("retrieval.seed_probe.http_get", return_value=html):
        result = probe_seed_url("https://example.com/members", _policy())
    assert result.status == SeedProbeStatus.STATIC_OK
    assert result.static_len > 0
    assert result.is_usable is True


def test_probe_blocked_when_both_empty() -> None:
    """Both http_get and obscura return empty → BLOCKED_OR_UNUSABLE."""
    with _no_obscura(), patch("retrieval.seed_probe.http_get", side_effect=OSError("403")):
        result = probe_seed_url("https://blocked.example.com", _policy())
    assert result.status == SeedProbeStatus.BLOCKED_OR_UNUSABLE
    assert result.is_usable is False


def test_probe_blocked_when_too_short() -> None:
    """Very short response (< _MIN_STATIC_CHARS) → BLOCKED_OR_UNUSABLE."""
    html = b"<html><body>Error</body></html>"
    with _no_obscura(), patch("retrieval.seed_probe.http_get", return_value=html):
        result = probe_seed_url("https://example.com", _policy())
    assert result.status == SeedProbeStatus.BLOCKED_OR_UNUSABLE


def test_probe_js_required_when_obscura_inflates() -> None:
    """Obscura returns much more text than static → JS_REQUIRED."""
    static_html = b"<html><body>" + b"x" * 50 + b"</body></html>"
    obscura_text = "Company Alpha\n" * 30  # 420 chars, much more than static
    import retrieval.seed_fetcher as sf
    with patch.object(sf, "_obscura_binary", return_value="/usr/bin/obscura"), \
         patch.object(sf, "_obscura_fetch_text", return_value=obscura_text), \
         patch("retrieval.seed_probe.http_get", return_value=static_html):
        result = probe_seed_url("https://js-heavy.example.com", _policy())
    assert result.status == SeedProbeStatus.JS_REQUIRED
    assert result.obscura_len > result.static_len
    assert result.is_usable is True


def test_probe_expected_terms_counted() -> None:
    """expected_terms that appear in content are counted."""
    html = b"<html><body>GIGABYTE Technology MSI International ASUS</body></html>" * 5
    with _no_obscura(), patch("retrieval.seed_probe.http_get", return_value=html):
        result = probe_seed_url(
            "https://example.com",
            _policy(),
            expected_terms=["GIGABYTE", "MSI", "nonexistent"],
        )
    assert result.expected_terms_hit == 2


def test_probe_returns_url_in_result() -> None:
    url = "https://example.com/test"
    with _no_obscura(), patch("retrieval.seed_probe.http_get", side_effect=OSError("fail")):
        result = probe_seed_url(url, _policy())
    assert result.url == url
