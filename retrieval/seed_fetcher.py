"""
Seed URL fetcher — fetches a URL and extracts candidate entity names.

Used by the controller to bootstrap the KeywordGraph before retrieval when
Intent.seed_urls is set. Typical use case: an exhibitor-list page, a distributor
directory, or any structured list of company names.

Extraction heuristics (ordered by confidence):
  1. <meta name="description"> — sometimes contains entity name
  2. Structured list items in <ul>/<ol> with short text (2–80 chars)
  3. Table cells in <td>/<th> with short text
  4. Link text in <a> tags within recognised container selectors
  5. <h2>/<h3> headings (short, title-case or CJK)

All results are length-filtered (3–80 chars) and deduplicated.
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
from typing import Any

from retrieval.http import http_get
from salva_core.schemas import RetrievalPolicy

logger = logging.getLogger("salva.retrieval.seed_fetcher")

_MIN_CHARS = 3
_MAX_CHARS = 80
_OBSCURA_TIMEOUT_MS = 15000

try:
    from bs4 import BeautifulSoup as _BS
    _BS4_AVAILABLE = True
except ImportError:
    _BS = None  # type: ignore[assignment,misc]
    _BS4_AVAILABLE = False


def _obscura_binary() -> str | None:
    custom = os.getenv("OBSCURA_BIN", "").strip()
    if custom:
        return custom if shutil.which(custom) else None
    return shutil.which("obscura")


def _obscura_fetch_text(url: str, timeout_ms: int = _OBSCURA_TIMEOUT_MS) -> str | None:
    """Render `url` via Obscura and return innerText, or None on failure."""
    binary = _obscura_binary()
    if not binary:
        return None
    cmd = [binary, "scrape", url, "--format", "json", "--eval", "document.body.innerText",
           "--timeout", str(timeout_ms), "--quiet"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_ms // 1000 + 10)
        raw = proc.stdout.strip()
        if not raw:
            return None
        parsed = json.loads(raw)
        results = parsed.get("results", [])
        if not results:
            return None
        return results[0].get("eval") or None
    except Exception as exc:
        logger.debug("seed_fetcher: obscura %s failed: %s", url, exc)
        return None


def fetch_entity_names(url: str, policy: RetrievalPolicy) -> list[str]:
    """
    Fetch `url` and return a deduplicated list of candidate entity names.
    Tries Obscura JS rendering first (when binary available), falls back to http_get.
    Returns an empty list on any network or parsing error.
    """
    # Try Obscura for JS-rendered pages
    text = _obscura_fetch_text(url, timeout_ms=int(policy.request_timeout * 1000))
    if text and len(text) > 50:
        logger.debug("seed_fetcher: obscura rendered %s (%d chars)", url, len(text))
        return _extract_from_text(text)

    # Static HTTP fallback
    try:
        raw = http_get(url, headers={"Accept": "text/html"}, timeout=policy.request_timeout)
        html = raw.decode("utf-8", errors="replace")
    except Exception as exc:
        logger.debug("seed_fetcher: fetch %s failed: %s", url, exc)
        return []

    if _BS4_AVAILABLE:
        return _extract_with_bs4(html)
    return _extract_regex(html)


def _extract_from_text(text: str) -> list[str]:
    """Extract entity names from Obscura's innerText output (plain text, one entry per line)."""
    candidates: list[str] = []
    for line in re.split(r"[\n\r]+", text):
        token = line.strip()
        if _is_valid_name(token):
            candidates.append(token)
    return _dedup(candidates)


def _extract_with_bs4(html: str) -> list[str]:
    soup = _BS(html, "html.parser")

    # Remove noise elements
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()

    candidates: list[str] = []

    # List items — highest signal for structured directories
    for li in soup.find_all("li"):
        text = li.get_text(separator=" ", strip=True)
        if _is_valid_name(text):
            candidates.append(text)

    # Table cells
    for cell in soup.find_all(["td", "th"]):
        text = cell.get_text(separator=" ", strip=True)
        if _is_valid_name(text):
            candidates.append(text)

    # Short headings
    for h in soup.find_all(["h2", "h3", "h4"]):
        text = h.get_text(separator=" ", strip=True)
        if _is_valid_name(text):
            candidates.append(text)

    # Link text (anchors)
    for a in soup.find_all("a", href=True):
        text = a.get_text(separator=" ", strip=True)
        if _is_valid_name(text):
            candidates.append(text)

    return _dedup(candidates)


def _extract_regex(html: str) -> list[str]:
    # Fallback when bs4 is not installed — simple tag stripping
    clean = re.sub(r"<[^>]+>", " ", html)
    tokens = re.split(r"[\n\r\t|,;]+", clean)
    candidates = [t.strip() for t in tokens if _is_valid_name(t.strip())]
    return _dedup(candidates)


def _is_valid_name(text: str) -> bool:
    if not text:
        return False
    if len(text) < _MIN_CHARS or len(text) > _MAX_CHARS:
        return False
    # Skip purely numeric or URL-like strings
    if re.fullmatch(r"[\d\s.,:;/\\-]+", text):
        return False
    if "://" in text or text.startswith("//"):
        return False
    return True


def _dedup(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.lower().strip()
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out
