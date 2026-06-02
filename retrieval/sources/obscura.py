"""
Obscura headless browser retrieval source.

Obscura is a Rust-based headless browser with V8 + CDP. It executes JavaScript,
bypasses basic bot protection, and supports parallel scraping. This provider
replaces site_html for radar/pirate strategies where JS execution matters.

https://github.com/h4ckf0r0day/obscura — Apache 2.0

Activation:
  - Binary auto-detected via shutil.which("obscura") or OBSCURA_BIN env var
  - Stealth mode: OBSCURA_STEALTH=true (anti-fingerprinting + tracker blocking)
  - Falls back to SiteHTMLRetriever transparently if binary is not found

Strategy assignment: radar (domain probing) + pirate (batch URL fetching)
"""
from __future__ import annotations

import json
import logging
import os
import random
import re
import shutil
import subprocess
import urllib.parse
import urllib.request
from html import unescape
from typing import Any

from retrieval.models import RetrievalAttempt
from salva_core.schemas import RetrievalPolicy

logger = logging.getLogger("salva.retrieval.obscura")

DDG_HTML_URL = "https://html.duckduckgo.com/html/"
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/123.0 Safari/537.36",
]
_BATCH_CONCURRENCY = 20
_BATCH_TIMEOUT_SEC = 60


def _find_obscura_binary() -> str | None:
    custom = os.getenv("OBSCURA_BIN", "").strip()
    if custom and shutil.which(custom):
        return custom
    return shutil.which("obscura")


class ObscuraBrowserRetriever:
    """
    Headless browser provider: uses Obscura for JS-rendered page fetching.
    If the binary is absent, transparently falls back to plain urllib (site_html mode).
    """

    strategy = "radar"

    def __init__(self, policy: RetrievalPolicy):
        self.policy = policy
        self.last_attempts: list[RetrievalAttempt] = []
        self._binary = _find_obscura_binary()
        self._stealth = policy.obscura_stealth or os.getenv("OBSCURA_STEALTH", "").lower() in ("1", "true", "yes")
        self._proxy = policy.proxy_url or os.getenv("OBSCURA_PROXY", "")

        if self._binary:
            logger.debug("Obscura binary: %s (stealth=%s)", self._binary, self._stealth)
        else:
            logger.info(
                "obscura binary not found — falling back to static HTML fetch. "
                "Install: https://github.com/h4ckf0r0day/obscura#install"
            )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def search(self, query: str, n: int = 10) -> list[dict[str, Any]]:
        self.last_attempts = []
        domains = self.policy.site_domains or _env_site_domains()
        if not domains:
            self.last_attempts.append(RetrievalAttempt(
                provider="obscura_browser",
                base_url="obscura_browser",
                mode=self.policy.mode,
                result_count=0,
                succeeded=False,
                error="no_site_domains",
                format_used="browser",
            ))
            return []

        results: list[dict[str, Any]] = []
        for domain in domains[: self.policy.max_instances_per_query]:
            site_query = f"site:{domain} {query}"
            candidate_urls = self._search_ddg(site_query, n=n)
            if not candidate_urls:
                self.last_attempts.append(RetrievalAttempt(
                    provider="obscura_browser",
                    base_url=domain,
                    mode=self.policy.mode,
                    result_count=0,
                    succeeded=False,
                    error="ddg_no_results",
                    format_used="browser",
                ))
                continue

            urls = [r["url"] for r in candidate_urls if r.get("url")]
            fetched = self._fetch_urls(urls, candidate_urls, n=n)
            results.extend(fetched)
            self.last_attempts.append(RetrievalAttempt(
                provider="obscura_browser",
                base_url=domain,
                mode=self.policy.mode,
                result_count=len(fetched),
                succeeded=bool(fetched),
                format_used="browser" if self._binary else "html",
            ))

        return results[:n]

    # ------------------------------------------------------------------
    # Internal: DDG URL discovery (same as site_html — finds URLs, not content)
    # ------------------------------------------------------------------

    def _search_ddg(self, query: str, n: int) -> list[dict[str, Any]]:
        data = urllib.parse.urlencode({"q": query}).encode()
        req = urllib.request.Request(
            DDG_HTML_URL,
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
            return _parse_ddg_html(html, n)
        except Exception as exc:
            logger.debug("obscura DDG search failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Internal: fetch URLs via Obscura or fallback
    # ------------------------------------------------------------------

    def _fetch_urls(
        self,
        urls: list[str],
        search_results: list[dict[str, Any]],
        n: int,
    ) -> list[dict[str, Any]]:
        if self._binary:
            return self._obscura_batch(urls, search_results, n)
        return self._urllib_batch(urls, search_results, n)

    def _obscura_batch(
        self,
        urls: list[str],
        search_results: list[dict[str, Any]],
        n: int,
    ) -> list[dict[str, Any]]:
        """
        obscura scrape url1 url2 ... --concurrency N --dump text --format json --quiet
        Outputs one JSON object per URL to stdout.
        """
        cmd = self._build_cmd() + [
            "scrape",
            *urls[:n],
            "--concurrency", str(min(_BATCH_CONCURRENCY, len(urls))),
            "--dump", "text",
            "--format", "json",
            "--quiet",
        ]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=_BATCH_TIMEOUT_SEC,
            )
            if proc.returncode != 0:
                logger.debug("obscura scrape non-zero exit %d: %s", proc.returncode, proc.stderr[:200])

            url_to_search = {r["url"]: r for r in search_results}
            items: list[dict[str, Any]] = []
            for line in proc.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                url = obj.get("url", "")
                text = obj.get("text") or obj.get("content") or ""
                base = url_to_search.get(url, {})
                items.append({
                    "title": obj.get("title") or base.get("title", ""),
                    "url": url,
                    "snippet": text[:500] if text else base.get("snippet", ""),
                    "engine": "obscura_browser",
                    "retrieval_instance": "obscura",
                    "page_text_excerpt": text[:1000] if text else "",
                })
            return items
        except subprocess.TimeoutExpired:
            logger.warning("obscura scrape timed out after %ds", _BATCH_TIMEOUT_SEC)
            return []
        except Exception as exc:
            logger.debug("obscura batch failed: %s", exc)
            return []

    def _urllib_batch(
        self,
        urls: list[str],
        search_results: list[dict[str, Any]],
        n: int,
    ) -> list[dict[str, Any]]:
        """Static HTTP fallback when Obscura binary is unavailable."""
        url_to_search = {r["url"]: r for r in search_results}
        items: list[dict[str, Any]] = []
        for url in urls[:n]:
            html = self._urllib_fetch(url)
            if not html:
                continue
            title, snippet = _parse_static_html(html)
            base = url_to_search.get(url, {})
            items.append({
                "title": title or base.get("title", ""),
                "url": url,
                "snippet": snippet or base.get("snippet", ""),
                "engine": "obscura_browser_fallback",
                "retrieval_instance": "urllib",
                "page_text_excerpt": snippet or "",
            })
        return items

    def _urllib_fetch(self, url: str) -> str | None:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": random.choice(USER_AGENTS)})
            with urllib.request.urlopen(req, timeout=self.policy.request_timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as exc:
            logger.debug("urllib fetch failed %s: %s", url, exc)
            return None

    def _build_cmd(self) -> list[str]:
        cmd: list[str] = []
        if self._proxy:
            cmd += [self._binary, "--proxy", self._proxy]  # type: ignore[list-item]
        else:
            cmd.append(self._binary)  # type: ignore[arg-type]
        return cmd


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _parse_ddg_html(html: str, n: int) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    blocks = re.findall(r'<div class="result(?:.|\n)*?</div>\s*</div>', html, flags=re.IGNORECASE)
    for block in blocks[:n]:
        title_m = re.search(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, flags=re.IGNORECASE | re.DOTALL)
        snip_m = re.search(r'class="result__snippet"[^>]*>(.*?)</(?:a|div)>', block, flags=re.IGNORECASE | re.DOTALL)
        if not title_m:
            continue
        results.append({
            "title": _strip_html(unescape(title_m.group(2))),
            "url": unescape(title_m.group(1)),
            "snippet": _strip_html(unescape(snip_m.group(1))) if snip_m else "",
            "engine": "ddg_html",
            "retrieval_instance": DDG_HTML_URL,
        })
    return results


def _parse_static_html(html: str) -> tuple[str | None, str | None]:
    title_m = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    title = _strip_html(unescape(title_m.group(1))) if title_m else None
    paras = re.findall(r"<p[^>]*>(.*?)</p>", html, flags=re.IGNORECASE | re.DOTALL)[:5]
    text = " ".join(_strip_html(unescape(p)) for p in paras if p)
    return title, text[:500] if text else None


def _strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(text.split())


def _env_site_domains() -> list[str]:
    return [
        item.strip().lower()
        for item in os.getenv("SITE_HTML_DOMAINS", "").split(",")
        if item.strip()
    ]
