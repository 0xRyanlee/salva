"""
Deduplication layer.

Primary key: normalized URL.
Secondary: BM25 title similarity for near-duplicate detection within same language.
Cross-language dedup requires Jina embeddings (wired when SALVA_SEMANTIC_VECTOR_BACKEND=jina_omlx).
"""
from __future__ import annotations

import hashlib
import re
from urllib.parse import urlparse, urlunparse

from core.types import UnifiedResult

# Default threshold — domain-calibrated values can be passed per-instance.
# B2B/hardware domains need higher threshold (0.92+) to avoid collapsing
# distinct companies that share industry terms (e.g. "outdoor distributor").
_BM25_THRESHOLD_DEFAULT = 0.82
_BM25_AVAILABLE: bool | None = None

# Domain-calibrated thresholds: higher = less aggressive dedup
BM25_DOMAIN_THRESHOLDS: dict[str, float] = {
    "bd_leads":        0.92,
    "companies":       0.92,
    "taiwan_hardware": 0.92,
    "partnerships":    0.90,
    "events":          0.82,
    "market_intel":    0.85,
    "general":         0.85,
}


def _bm25_available() -> bool:
    global _BM25_AVAILABLE
    if _BM25_AVAILABLE is None:
        try:
            import rank_bm25  # noqa: F401
            _BM25_AVAILABLE = True
        except ImportError:
            _BM25_AVAILABLE = False
    return _BM25_AVAILABLE


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[\w一-鿿]+", text.lower())


def _bm25_similarity(query_tokens: list[str], corpus_docs: list[list[str]]) -> list[float]:
    from rank_bm25 import BM25Okapi
    if not corpus_docs:
        return []
    bm25 = BM25Okapi(corpus_docs)
    scores = bm25.get_scores(query_tokens)
    max_s = max(scores) if scores.any() else 1.0
    return [float(s / max_s) if max_s > 0 else 0.0 for s in scores]


class MemoryDeduplicator:
    """
    In-memory deduplicator for a single run.
    For cross-run dedup, use PersistentDeduplicator backed by a DB.
    """

    def __init__(
        self,
        fuzzy_title: bool = False,
        bm25_dedup: bool = True,
        bm25_threshold: float = _BM25_THRESHOLD_DEFAULT,
    ):
        self._seen_keys: set[str] = set()
        self._seen_domains: dict[str, int] = {}
        self._registered: list[UnifiedResult] = []
        self._registered_tokens: list[list[str]] = []
        self.fuzzy_title = fuzzy_title
        self.bm25_dedup = bm25_dedup and _bm25_available()
        self.bm25_threshold = bm25_threshold

    def is_duplicate(self, result: UnifiedResult) -> bool:
        key = self._result_key(result)
        if key in self._seen_keys:
            return True

        if self.bm25_dedup and result.title and self._registered_tokens:
            qtok = _tokenize(result.title)
            if qtok:
                scores = _bm25_similarity(qtok, self._registered_tokens)
                if scores and max(scores) >= self.bm25_threshold:
                    return True

        return False

    def register(self, result: UnifiedResult) -> None:
        key = self._result_key(result)
        self._seen_keys.add(key)
        self._registered.append(result)
        self._registered_tokens.append(_tokenize(result.title or ""))

        domain = urlparse(result.source_url).netloc
        self._seen_domains[domain] = self._seen_domains.get(domain, 0) + 1

    def domain_count(self, domain: str) -> int:
        return self._seen_domains.get(domain, 0)

    @staticmethod
    def _normalize_url(url: str) -> str:
        if not url:
            return ""
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
