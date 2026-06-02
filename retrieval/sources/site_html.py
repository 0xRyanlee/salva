from __future__ import annotations

import logging
import os
import random
import re
import time
import urllib.parse
import urllib.request
from html import unescape
from types import ModuleType
from typing import Any, cast

from retrieval.models import RetrievalAttempt
from salva_core.schemas import RetrievalPolicy

logger = logging.getLogger("salva.retrieval.site_html")

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/123.0 Safari/537.36",
]

try:
    import bs4 as _bs4_module
except Exception:  # pragma: no cover - optional dependency
    bs4: ModuleType | None = None
else:
    bs4 = _bs4_module


class SiteHTMLRetriever:
    strategy = "radar"

    def __init__(self, policy: RetrievalPolicy):
        self.policy = policy
        self.last_attempts: list[RetrievalAttempt] = []

    def search(self, query: str, n: int = 10) -> list[dict[str, Any]]:
        self.last_attempts = []
        domains = self.policy.site_domains or _env_site_domains()
        if not domains:
            self.last_attempts.append(
                RetrievalAttempt(
                    provider="site_html",
                    base_url="site_html",
                    mode=self.policy.mode,
                    result_count=0,
                    succeeded=False,
                    error="no_site_domains",
                    format_used="html",
                )
            )
            return []

        results: list[dict[str, Any]] = []
        for domain in domains[: self.policy.max_instances_per_query]:
            site_query = f"site:{domain} {query}"
            search_results = self._search_ddg(site_query, n=n)
            fetched = self._fetch_and_parse(search_results, domain, n=n)
            results.extend(fetched)
            self.last_attempts.append(
                RetrievalAttempt(
                    provider="site_html",
                    base_url=domain,
                    mode=self.policy.mode,
                    result_count=len(fetched),
                    succeeded=bool(fetched),
                    format_used="html+bs4" if bs4 is not None else "html",
                )
            )

        return results[:n]

    def _search_ddg(self, query: str, n: int) -> list[dict[str, Any]]:
        url = "https://html.duckduckgo.com/html/"
        data = urllib.parse.urlencode({"q": query}).encode()
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "User-Agent": random.choice(USER_AGENTS),
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "text/html,application/xhtml+xml",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.policy.request_timeout) as resp:
                html = resp.read().decode("utf-8", errors="replace")
            time.sleep(self.policy.request_delay)
            return _parse_ddg_html(html, n)
        except Exception as exc:
            logger.debug("site_html DDG search failed: %s", exc)
            return []

    def _fetch_and_parse(self, results: list[dict[str, Any]], domain: str, n: int) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for result in results[:n]:
            url = result.get("url", "")
            if not isinstance(url, str) or not url:
                continue
            html = self._fetch_url(url)
            if not html:
                continue
            title, snippet, extra_tags = _parse_page(html)
            item = {
                "title": title or result.get("title", ""),
                "url": url,
                "snippet": snippet or result.get("snippet", ""),
                "engine": "site_html",
                "retrieval_instance": domain,
                "page_title": title,
                "page_text_excerpt": snippet,
                "page_tags": extra_tags,
            }
            items.append(item)
        return items

    def _fetch_url(self, url: str) -> str | None:
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": random.choice(USER_AGENTS)},
            )
            with urllib.request.urlopen(req, timeout=self.policy.request_timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as exc:
            logger.debug("site_html fetch failed %s: %s", url, exc)
            return None


def _parse_ddg_html(html: str, n: int) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    blocks = re.findall(
        r'<div class="result(?:.|\n)*?</div>\s*</div>',
        html,
        flags=re.IGNORECASE,
    )
    for block in blocks[:n]:
        title_match = re.search(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, flags=re.IGNORECASE | re.DOTALL)
        snippet_match = re.search(r'class="result__snippet"[^>]*>(.*?)</a>|class="result__snippet"[^>]*>(.*?)</div>', block, flags=re.IGNORECASE | re.DOTALL)
        if not title_match:
            continue
        url = unescape(title_match.group(1))
        title = _strip_html(unescape(title_match.group(2)))
        snippet_raw = snippet_match.group(1) or snippet_match.group(2) if snippet_match else ""
        results.append(
            {
                "title": title,
                "url": url,
                "snippet": _strip_html(unescape(snippet_raw or "")),
                "engine": "ddg_html",
                "retrieval_instance": "site_html",
            }
        )
    return results


def _parse_page(html: str) -> tuple[str | None, str | None, list[str]]:
    if bs4 is not None:
        soup = bs4.BeautifulSoup(html, "html.parser")
        title = soup.title.get_text(" ", strip=True) if soup.title else None
        paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")[:5]]
        headings = [h.get_text(" ", strip=True) for h in soup.find_all(re.compile("^h[1-4]$"))[:5]]
        text_bits = [text for text in [title, *headings, *paragraphs] if text is not None]
        tags = [cast(str, tag.name) for tag in soup.find_all(["meta", "h1", "h2", "h3", "h4"])[:10] if getattr(tag, "name", None)]
        return title, " ".join(text_bits)[:500], tags

    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    title = _strip_html(unescape(title_match.group(1))) if title_match else None
    paragraphs = re.findall(r"<p[^>]*>(.*?)</p>", html, flags=re.IGNORECASE | re.DOTALL)[:5]
    text_bits = [text for text in [title, *[_strip_html(unescape(p)) for p in paragraphs if p]] if text is not None]
    return title, " ".join(text_bits)[:500], []


def _strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(text.split())


def _env_site_domains() -> list[str]:
    return [
        item.strip().lower()
        for item in os.getenv("SITE_HTML_DOMAINS", "").split(",")
        if item.strip()
    ]
