"""
Deduplication layer.

Dedup dimensions (from 7 流程架構規格.md):
    domain, source_url, title similarity, organizer_email

Uses exact URL matching as primary key.
Optional fuzzy title matching for near-duplicates.
"""
from __future__ import annotations
import hashlib
from urllib.parse import urlparse

from core.types import UnifiedResult


class MemoryDeduplicator:
    """
    In-memory deduplicator for a single run.
    For cross-run dedup, use PersistentDeduplicator backed by a DB.
    """

    def __init__(self, fuzzy_title: bool = False):
        self._seen_keys: set[str] = set()
        self._seen_domains: dict[str, int] = {}    # domain → count
        self.fuzzy_title = fuzzy_title

    def is_duplicate(self, result: UnifiedResult) -> bool:
        key = self._result_key(result)
        if key in self._seen_keys:
            return True

        return False

    def register(self, result: UnifiedResult) -> None:
        key = self._result_key(result)
        self._seen_keys.add(key)

        domain = urlparse(result.source_url).netloc
        self._seen_domains[domain] = self._seen_domains.get(domain, 0) + 1

    def domain_count(self, domain: str) -> int:
        return self._seen_domains.get(domain, 0)

    @staticmethod
    def _normalize_url(url: str) -> str:
        if not url:
            return ""
        from urllib.parse import urlparse, urlunparse
        parsed = urlparse(url)
        return urlunparse((parsed.scheme or "https", parsed.netloc.lower(), parsed.path.rstrip("/"), "", "", ""))

    @staticmethod
    def _title_hash(title: str) -> str:
        normalized = " ".join(title.lower().split()[:6])
        return hashlib.md5(normalized.encode()).hexdigest()

    def _result_key(self, result: UnifiedResult) -> str:
        url = self._normalize_url(result.source_url)
        title = self._title_hash(result.title) if result.title else ""
        domain = urlparse(result.source_url).netloc.lower().removeprefix("www.")
        return f"{domain}|{url}|{title}"
