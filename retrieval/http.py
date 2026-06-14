"""
Thin HTTP helper with curl_cffi TLS-impersonation when available.

When `curl_cffi` is installed, GET and POST requests use browser JA3/TLS fingerprint
spoofing to bypass bot-detection on public search endpoints. Falls back to standard
`urllib.request` when the package is absent, so the retrieval layer degrades gracefully.

Public surface:
  http_get(url, headers, timeout)  → bytes
  http_post(url, data, headers, timeout) → bytes
  CURL_CFFI_AVAILABLE: bool
"""
from __future__ import annotations

import urllib.parse
import urllib.request
from typing import Any

try:
    from curl_cffi import requests as _cffi_requests
    CURL_CFFI_AVAILABLE = True
except ImportError:
    _cffi_requests = None  # type: ignore[assignment]
    CURL_CFFI_AVAILABLE = False

_DEFAULT_IMPERSONATE = "chrome136"


def http_get(
    url: str,
    headers: dict[str, str] | None = None,
    timeout: float = 15.0,
) -> bytes:
    if CURL_CFFI_AVAILABLE:
        resp = _cffi_requests.get(
            url,
            headers=headers or {},
            timeout=timeout,
            impersonate=_DEFAULT_IMPERSONATE,
        )
        resp.raise_for_status()
        return resp.content

    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def http_post(
    url: str,
    data: bytes,
    headers: dict[str, str] | None = None,
    timeout: float = 15.0,
) -> bytes:
    if CURL_CFFI_AVAILABLE:
        resp = _cffi_requests.post(
            url,
            data=data,
            headers=headers or {},
            timeout=timeout,
            impersonate=_DEFAULT_IMPERSONATE,
        )
        resp.raise_for_status()
        return resp.content

    req = urllib.request.Request(url, data=data, headers=headers or {}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()
