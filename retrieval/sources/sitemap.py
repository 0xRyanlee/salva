"""Sitemap-first source-direct retriever.

Discovery path:
  1. Fetch robots.txt → extract Sitemap: lines
  2. Fetch each sitemap.xml / sitemap_index.xml
  3. Parse <url><loc> entries
  4. Filter by URL path keywords (partner, dealer, distributor, member, exhibitor, etc.)
  5. Return as retrieval results with url + title extracted from <image:title> or path

This is a source-direct retriever (no search engine involved). It is called
explicitly when the intent has seed_domains set, or added to the radar strategy
chain for deep domain probing.
"""
from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import urljoin, urlparse

from retrieval.http import http_get
from salva_core.schemas import RetrievalPolicy

logger = logging.getLogger("salva.retrieval.sitemap")

# URL path keywords that suggest entity directory pages
_DIRECTORY_KEYWORDS = {
    "partner", "dealer", "distributor", "wholesale", "reseller",
    "member", "exhibitor", "sponsor", "vendor", "supplier",
    "directory", "listing", "companies", "brands", "affiliates",
    "contact", "about", "join", "network",
}

_MAX_SITEMAP_URLS = 500   # guard against huge sitemaps
_MAX_DEPTH = 2            # max sitemap index nesting depth


class SitemapRetriever:
    """Fetch sitemap from a domain and return directory-like candidate URLs."""

    strategy = "anchor"

    def __init__(self, policy: RetrievalPolicy) -> None:
        self.policy = policy
        self.last_attempts: list[dict] = []

    def search(self, query: str, n: int = 10) -> list[dict[str, Any]]:
        """Not used in the standard search path; call discover_domain() directly."""
        return []

    def discover_domain(self, base_url: str, n: int = 20) -> list[dict[str, Any]]:
        """
        Fetch sitemap for `base_url` and return up to `n` directory-like candidate URLs.
        """
        self.last_attempts = []
        parsed = urlparse(base_url)
        origin = f"{parsed.scheme}://{parsed.netloc}"

        sitemap_urls = self._find_sitemap_urls(origin)
        if not sitemap_urls:
            logger.debug("sitemap: no sitemaps found for %s", origin)
            return []

        all_locs: list[str] = []
        for sm_url in sitemap_urls[:5]:
            locs = self._fetch_sitemap(sm_url, depth=0)
            all_locs.extend(locs)
            if len(all_locs) >= _MAX_SITEMAP_URLS:
                break

        candidates = self._filter_directory_urls(all_locs, n=n)
        results: list[dict[str, Any]] = []
        for url in candidates:
            path = urlparse(url).path.strip("/")
            title = path.replace("/", " › ").replace("-", " ").replace("_", " ").title()
            results.append({
                "title": title,
                "url": url,
                "snippet": f"Sitemap candidate: {url}",
                "engine": "sitemap",
                "retrieval_instance": origin,
            })
        self.last_attempts.append({
            "provider": "sitemap",
            "base_url": origin,
            "result_count": len(results),
            "succeeded": bool(results),
        })
        return results

    # ------------------------------------------------------------------

    def _find_sitemap_urls(self, origin: str) -> list[str]:
        """Try robots.txt first, then common fallback paths."""
        sitemaps: list[str] = []
        try:
            raw = http_get(f"{origin}/robots.txt", timeout=self.policy.request_timeout)
            text = raw.decode("utf-8", errors="replace")
            for line in text.splitlines():
                if line.lower().startswith("sitemap:"):
                    url = line.split(":", 1)[1].strip()
                    if url:
                        sitemaps.append(url)
        except Exception:
            pass

        if not sitemaps:
            for fallback in ["/sitemap.xml", "/sitemap_index.xml", "/sitemap-index.xml"]:
                url = origin + fallback
                try:
                    http_get(url, timeout=self.policy.request_timeout)
                    sitemaps.append(url)
                    break
                except Exception:
                    pass
        return sitemaps

    def _fetch_sitemap(self, url: str, depth: int) -> list[str]:
        if depth > _MAX_DEPTH:
            return []
        try:
            raw = http_get(url, timeout=self.policy.request_timeout)
            text = raw.decode("utf-8", errors="replace")
        except Exception as exc:
            logger.debug("sitemap fetch failed %s: %s", url, exc)
            return []

        try:
            root = ET.fromstring(text)
        except ET.ParseError:
            return []

        ns = self._namespace(root.tag)
        locs: list[str] = []

        # Sitemap index → recurse
        for sitemap_el in root.findall(f"{ns}sitemap"):
            loc_el = sitemap_el.find(f"{ns}loc")
            if loc_el is not None and loc_el.text:
                sub_locs = self._fetch_sitemap(loc_el.text.strip(), depth + 1)
                locs.extend(sub_locs)
                if len(locs) >= _MAX_SITEMAP_URLS:
                    return locs[:_MAX_SITEMAP_URLS]

        # Sitemap with URLs
        for url_el in root.findall(f"{ns}url"):
            loc_el = url_el.find(f"{ns}loc")
            if loc_el is not None and loc_el.text:
                locs.append(loc_el.text.strip())
            if len(locs) >= _MAX_SITEMAP_URLS:
                break

        return locs

    def _filter_directory_urls(self, locs: list[str], n: int) -> list[str]:
        scored: list[tuple[int, str]] = []
        for loc in locs:
            path = urlparse(loc).path.lower()
            score = sum(1 for kw in _DIRECTORY_KEYWORDS if kw in path)
            if score > 0:
                scored.append((score, loc))
        scored.sort(key=lambda x: -x[0])
        return [loc for _, loc in scored[:n]]

    @staticmethod
    def _namespace(tag: str) -> str:
        if tag.startswith("{"):
            return tag[: tag.index("}") + 1]  # e.g. "{http://...}"
        return ""
