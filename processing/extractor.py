"""
Extraction layer — converts raw search results into UnifiedResult objects.

Handles:
- title/snippet normalization
- email/domain extraction (regex, from BDDB osint_crawler.py)
- domain parsing
- datetime parsing (for event-domain results)
"""
from __future__ import annotations
import re
import logging
from datetime import UTC, datetime
from urllib.parse import urlparse

from core.types import UnifiedResult
from processing.pipeline import ProcessingPipeline

logger = logging.getLogger("salva.processing.extractor")

_EMAIL_RE = re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+')
_DATE_PATTERNS = [
    r'\d{4}[-/]\d{2}[-/]\d{2}',
    r'\d{2}[-/]\d{2}[-/]\d{4}',
]


class BaseExtractor:
    """
    Generic extractor for web-search results.
    Override `extract()` in domain adapters (PartyExtractor, BDDBExtractor)
    for custom field mapping.
    """

    def __init__(self, pipeline: ProcessingPipeline | None = None):
        self.pipeline = pipeline or ProcessingPipeline()

    def extract(
        self,
        raw: dict,
        query: str,
        round_num: int,
        strategy: str,
    ) -> UnifiedResult | None:
        processed = self.pipeline.process(raw, query, strategy)
        if not processed.accepted:
            logger.debug(
                "Prefilter rejected result for query=%s strategy=%s reason=%s",
                query,
                strategy,
                processed.prefilter_reason,
            )
            return None
        normalized = processed.normalized
        url = normalized.get("url", "").strip()
        title = normalized.get("title", "").strip()
        snippet = normalized.get("snippet", "").strip()

        if not url or not title:
            return None

        domain = urlparse(url).netloc
        text = f"{title} {snippet}"

        emails = _EMAIL_RE.findall(text)
        starts_at = self._parse_date(snippet)
        raw_evidence = {
            "raw": dict(raw),
            "normalized": dict(normalized),
            "classification": dict(processed.classification),
            "dedupe_key": processed.dedupe_key,
            "prefilter_reason": processed.prefilter_reason,
        }

        return UnifiedResult(
            source_name=normalized.get("engine", "searxng"),
            source_url=url,
            title=title[:200],
            description=snippet[:500],
            organizer_domain=domain,
            organizer_email=emails[0] if emails else None,
            starts_at=starts_at,
            discovered_at=datetime.now(UTC),
            round_num=round_num,
            query_used=query,
            strategy_used=strategy,
            tags=[
                processed.classification["content_type"],
                processed.classification["source_kind"],
            ],
            raw_evidence=raw_evidence,
        )

    @staticmethod
    def _parse_date(text: str) -> datetime | None:
        for pat in _DATE_PATTERNS:
            m = re.search(pat, text)
            if m:
                for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%d-%m-%Y"):
                    try:
                        return datetime.strptime(m.group(), fmt)
                    except ValueError:
                        continue
        return None
