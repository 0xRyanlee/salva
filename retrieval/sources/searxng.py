"""
SearXNG retrieval source with resilient fallback behavior.

Supports:
- local instance first
- built-in public instance pools
- environment-configured extra mirrors
- JSON API first, HTML parsing fallback
- instance cooldown after failures
- engine rotation
- wall-guarded mode for more defensive fallback behavior
"""
from __future__ import annotations

import json
import logging
import os
import random
import re
import time
import urllib.parse
from html import unescape
from typing import Any

from retrieval.http import http_get
from retrieval.models import RetrievalAttempt
from salva_core.schemas import RetrievalPolicy

logger = logging.getLogger("salva.retrieval.searxng")

DEFAULT_LOCAL_INSTANCE = os.getenv("SEARXNG_URL", "http://localhost:8080")

PUBLIC_INSTANCE_POOLS: dict[str, list[str]] = {
    "default": [
        "https://searx.be",
        "https://search.bus-hit.me",
        "https://searx.tiekoetter.com",
        "https://paulgo.io",
    ],
    "wall_guarded": [
        "https://searx.be",
        "https://search.bus-hit.me",
        "https://searx.tiekoetter.com",
        "https://priv.au",
        "https://northboot.xyz",
    ],
}

ENGINE_ROTATION = [
    "google,bing,duckduckgo",
    "duckduckgo,startpage,qwant",
    "bing,brave,duckduckgo",
]

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/123.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0 Safari/537.36",
]

_FAILED_UNTIL: dict[str, float] = {}


class SearXNGRetriever:
    strategy = "dive"

    def __init__(
        self,
        policy: RetrievalPolicy,
        base_url: str = DEFAULT_LOCAL_INSTANCE,
    ):
        self.base_url = base_url.rstrip("/")
        self.policy = policy
        self._engine_index = 0
        self.last_attempts: list[RetrievalAttempt] = []

    def search(self, query: str, n: int = 10) -> list[dict[str, Any]]:
        self.last_attempts = []

        for index, instance in enumerate(self._candidate_instances()):
            if index >= self.policy.max_instances_per_query:
                break
            if self._is_cooled_down(instance):
                continue

            engine_bundle = self._next_engines()
            results, format_used, error = self._search_instance(instance, query, n, engine_bundle)
            self.last_attempts.append(
                RetrievalAttempt(
                    provider="searxng",
                    base_url=instance,
                    mode=self.policy.mode,
                    result_count=len(results),
                    succeeded=bool(results),
                    error=error,
                    format_used=format_used,
                )
            )

            if results:
                return results

            self._mark_failure(instance, error or "empty_result")

        return []

    def _candidate_instances(self) -> list[str]:
        instances: list[str] = []
        if self.policy.local_first and self.base_url:
            instances.append(self.base_url)

        if self.policy.allow_public_fallback and self.policy.prefer_builtin_instances:
            pool_name = "wall_guarded" if self.policy.mode == "wall_guarded" else "default"
            instances.extend(PUBLIC_INSTANCE_POOLS.get(pool_name, []))

        instances.extend(self._env_extra_instances())
        instances.extend(self.policy.extra_instances)

        deduped: list[str] = []
        seen: set[str] = set()
        for item in instances:
            normalized = item.rstrip("/")
            if normalized and normalized not in seen:
                seen.add(normalized)
                deduped.append(normalized)
        return deduped

    def _search_instance(
        self,
        base: str,
        query: str,
        n: int,
        engines: str,
    ) -> tuple[list[dict[str, Any]], str | None, str | None]:
        json_results, json_error = self._search_json(base, query, n, engines)
        if json_results:
            return json_results, "json", None

        if self.policy.html_fallback:
            html_results, html_error = self._search_html(base, query, n)
            if html_results:
                return html_results, "html", None
            return [], None, html_error or json_error

        return [], None, json_error

    def _search_json(
        self,
        base: str,
        query: str,
        n: int,
        engines: str,
    ) -> tuple[list[dict[str, Any]], str | None]:
        search_params: dict[str, str | int] = {
            "q": query,
            "format": "json",
            "engines": engines,
            "limit": n,
        }
        if self.policy.region_hint:
            # e.g. "de-de" → language="de", region="de-de"
            lang = self.policy.region_hint.split("-")[0]
            search_params["language"] = lang
            search_params["region"] = self.policy.region_hint
        params = urllib.parse.urlencode(search_params)
        url = f"{base}/search?{params}"
        try:
            raw = http_get(
                url,
                headers={
                    "User-Agent": random.choice(USER_AGENTS),
                    "Accept": "application/json",
                },
                timeout=self.policy.request_timeout,
            )
            data = json.loads(raw)
            self._pace()
            return [
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": r.get("content", ""),
                    "engine": r.get("engine", ""),
                    "retrieval_instance": base,
                }
                for r in data.get("results", [])[:n]
                if r.get("url")
            ], None
        except Exception as exc:
            logger.debug("SearXNG JSON %s failed: %s", base, exc)
            return [], str(exc)

    def _search_html(self, base: str, query: str, n: int) -> tuple[list[dict[str, Any]], str | None]:
        params = urllib.parse.urlencode({"q": query})
        url = f"{base}/search?{params}"
        try:
            raw = http_get(
                url,
                headers={
                    "User-Agent": random.choice(USER_AGENTS),
                    "Accept": "text/html,application/xhtml+xml",
                },
                timeout=self.policy.request_timeout,
            )
            html = raw.decode("utf-8", errors="replace")
            self._pace()
            return self._parse_html_results(html, n, base), None
        except Exception as exc:
            logger.debug("SearXNG HTML %s failed: %s", base, exc)
            return [], str(exc)

    def _parse_html_results(self, html: str, n: int, base: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        blocks = re.findall(
            r'<article[^>]*class="[^"]*result[^"]*"[\s\S]*?</article>',
            html,
            flags=re.IGNORECASE,
        )
        if not blocks:
            blocks = re.findall(r'<div[^>]*class="[^"]*result[^"]*"[\s\S]*?</div>', html, flags=re.IGNORECASE)

        for block in blocks[:n]:
            url_match = re.search(r'href="([^"]+)"', block)
            title_match = re.search(r'<h[2-4][^>]*>([\s\S]*?)</h[2-4]>', block, flags=re.IGNORECASE)
            snippet_match = re.search(
                r'<(?:p|div)[^>]*class="[^"]*(?:content|snippet)[^"]*"[^>]*>([\s\S]*?)</(?:p|div)>',
                block,
                flags=re.IGNORECASE,
            )
            if not url_match:
                continue

            results.append(
                {
                    "title": _strip_html(unescape(title_match.group(1))) if title_match else "",
                    "url": unescape(url_match.group(1)),
                    "snippet": _strip_html(unescape(snippet_match.group(1))) if snippet_match else "",
                    "engine": "html_fallback",
                    "retrieval_instance": base,
                }
            )
        return results

    def _next_engines(self) -> str:
        if not self.policy.engine_rotation:
            return ENGINE_ROTATION[0]
        engines = ENGINE_ROTATION[self._engine_index % len(ENGINE_ROTATION)]
        self._engine_index += 1
        return engines

    def _pace(self) -> None:
        if self.policy.request_delay > 0:
            time.sleep(self.policy.request_delay)

    def _is_cooled_down(self, base: str) -> bool:
        until = _FAILED_UNTIL.get(base, 0.0)
        return until > time.time()

    def _mark_failure(self, base: str, reason: str) -> None:
        _FAILED_UNTIL[base] = time.time() + self.policy.cooldown_seconds
        logger.debug("Cooling down %s for %.1fs because %s", base, self.policy.cooldown_seconds, reason)

    @staticmethod
    def _env_extra_instances() -> list[str]:
        configured = os.getenv("SEARXNG_FALLBACK_URLS", "")
        return [item.strip() for item in configured.split(",") if item.strip()]


def _strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(text.split())
