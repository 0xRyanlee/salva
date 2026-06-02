from __future__ import annotations

import logging
import random
import re
import time
import urllib.parse
import urllib.request
from html import unescape
from typing import Any

from retrieval.models import RetrievalAttempt
from salva_core.schemas import RetrievalPolicy

logger = logging.getLogger("salva.retrieval.ddg_html")

DDG_HTML_URL = "https://html.duckduckgo.com/html/"

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/123.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0 Safari/537.36",
]


class DDGHTMLRetriever:
    strategy = "radar"

    def __init__(self, policy: RetrievalPolicy, base_url: str | None = DDG_HTML_URL):
        self.policy = policy
        self.base_url = base_url or DDG_HTML_URL
        self.last_attempts: list[RetrievalAttempt] = []

    def search(self, query: str, n: int = 10) -> list[dict[str, Any]]:
        self.last_attempts = []
        try:
            data = urllib.parse.urlencode({"q": query}).encode()
            req = urllib.request.Request(
                self.base_url,
                data=data,
                headers={
                    "User-Agent": random.choice(USER_AGENTS),
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "text/html,application/xhtml+xml",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self.policy.request_timeout) as resp:
                html = resp.read().decode("utf-8", errors="replace")
            time.sleep(self.policy.request_delay)
            results = _parse_ddg_html(html, n)
            self.last_attempts.append(
                RetrievalAttempt(
                    provider="ddg_html",
                    base_url=self.base_url,
                    mode=self.policy.mode,
                    result_count=len(results),
                    succeeded=bool(results),
                    format_used="html",
                )
            )
            return results
        except Exception as exc:
            logger.debug("DDG HTML failed: %s", exc)
            self.last_attempts.append(
                RetrievalAttempt(
                    provider="ddg_html",
                    base_url=self.base_url,
                    mode=self.policy.mode,
                    result_count=0,
                    succeeded=False,
                    error=str(exc),
                    format_used="html",
                )
            )
            return []


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
                "retrieval_instance": DDG_HTML_URL,
            }
        )
    return results


def _strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(text.split())
