"""RSS / Atom feed retriever — source-direct news and update discovery.

Discovery path:
  1. Detect feed URL (try common paths: /feed, /rss, /atom.xml, /blog/feed, etc.)
  2. Fetch and parse Atom or RSS 2.0 feed
  3. Return entries as retrieval results (title + link + summary)

Useful for:
  - Foundation/membership news (member announcements)
  - Company blogs (product launches, partner announcements)
  - Trade press feeds (industry directories, event coverage)
"""
from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import urljoin, urlparse

from retrieval.http import http_get
from salva_core.schemas import RetrievalPolicy

logger = logging.getLogger("salva.retrieval.rss")

_FEED_PATHS = [
    "/feed", "/rss", "/atom.xml", "/feed.xml", "/rss.xml",
    "/blog/feed", "/blog/rss", "/news/feed", "/news/rss",
    "/feed/rss", "/feed/atom",
]
_MAX_ENTRIES = 50

# XML namespaces
_NS_ATOM = "{http://www.w3.org/2005/Atom}"
_NS_CONTENT = "{http://purl.org/rss/1.0/modules/content/}"
_NS_MEDIA = "{http://search.yahoo.com/mrss/}"


class RSSRetriever:
    """Fetch RSS/Atom feed for a domain and return entries as retrieval results."""

    strategy = "anchor"

    def __init__(self, policy: RetrievalPolicy) -> None:
        self.policy = policy
        self.last_attempts: list[dict] = []

    def search(self, query: str, n: int = 10) -> list[dict[str, Any]]:
        """Not used in standard search path; call fetch_feed() directly."""
        return []

    def fetch_feed(self, base_url: str, n: int = _MAX_ENTRIES) -> list[dict[str, Any]]:
        """
        Auto-detect and fetch feed for `base_url`, return up to `n` entries.
        """
        self.last_attempts = []
        parsed = urlparse(base_url)
        origin = f"{parsed.scheme}://{parsed.netloc}"

        feed_url = self._detect_feed(origin)
        if not feed_url:
            logger.debug("rss: no feed found for %s", origin)
            return []

        try:
            raw = http_get(feed_url, timeout=self.policy.request_timeout)
            text = raw.decode("utf-8", errors="replace")
        except Exception as exc:
            logger.debug("rss fetch failed %s: %s", feed_url, exc)
            return []

        entries = self._parse(text, n)
        self.last_attempts.append({
            "provider": "rss",
            "base_url": origin,
            "feed_url": feed_url,
            "result_count": len(entries),
            "succeeded": bool(entries),
        })
        return entries

    # ------------------------------------------------------------------

    def _detect_feed(self, origin: str) -> str | None:
        for path in _FEED_PATHS:
            url = origin + path
            try:
                raw = http_get(url, timeout=min(self.policy.request_timeout, 8))
                text = raw.decode("utf-8", errors="replace")[:200]
                if "<rss" in text or "<feed" in text or "<channel" in text:
                    return url
            except Exception:
                continue
        return None

    def _parse(self, text: str, n: int) -> list[dict[str, Any]]:
        try:
            root = ET.fromstring(text)
        except ET.ParseError as exc:
            logger.debug("rss parse error: %s", exc)
            return []

        tag = root.tag.lower()
        if "feed" in tag:
            return self._parse_atom(root, n)
        return self._parse_rss(root, n)

    def _parse_atom(self, root: ET.Element, n: int) -> list[dict[str, Any]]:
        results = []
        for entry in root.findall(f"{_NS_ATOM}entry")[:n]:
            title_el = entry.find(f"{_NS_ATOM}title")
            link_el = entry.find(f"{_NS_ATOM}link")
            summary_el = entry.find(f"{_NS_ATOM}summary")
            if summary_el is None:
                summary_el = entry.find(f"{_NS_ATOM}content")
            title = (title_el.text or "").strip() if title_el is not None else ""
            url = link_el.get("href", "") if link_el is not None else ""
            snippet = _strip_html((summary_el.text or "") if summary_el is not None else "")[:300]
            if title and url:
                results.append({"title": title, "url": url, "snippet": snippet,
                                 "engine": "rss_atom", "retrieval_instance": "rss"})
        return results

    def _parse_rss(self, root: ET.Element, n: int) -> list[dict[str, Any]]:
        results = []
        channel = root.find("channel")
        if channel is None:
            channel = root
        for item in channel.findall("item")[:n]:
            title_el = item.find("title")
            link_el = item.find("link")
            desc_el = item.find("description")
            title = (title_el.text or "").strip() if title_el is not None else ""
            url = (link_el.text or "").strip() if link_el is not None else ""
            snippet = _strip_html((desc_el.text or "") if desc_el is not None else "")[:300]
            if title and url:
                results.append({"title": title, "url": url, "snippet": snippet,
                                 "engine": "rss", "retrieval_instance": "rss"})
        return results


def _strip_html(text: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", text).split())
