"""
Processing pipeline helpers.

This module keeps the deterministic parts of the pipeline explicit:
- normalize raw fetch results
- classify content and source shape
- derive stable dedupe keys
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse, urlunparse


_WHITESPACE_RE = re.compile(r"\s+")
_EVENT_HINTS = ("event", "meetup", "workshop", "expo", "conference", "webinar", "seminar", "活動", "講座")
_COMPANY_HINTS = ("company", "about", "team", "investor", "careers", "press", "brand")
_CONTACT_HINTS = ("@","mailto:", "contact", "sales", "business", "partnership")


@dataclass(frozen=True)
class ProcessingResult:
    accepted: bool
    prefilter_reason: str | None
    normalized: dict[str, Any]
    classification: dict[str, Any]
    dedupe_key: str


class ProcessingPipeline:
    def prefilter(self, raw: dict[str, Any], query: str, strategy: str) -> tuple[bool, str | None]:
        text = f"{raw.get('title', '')} {raw.get('snippet', '')} {query}".lower()
        title = self._normalize_text(str(raw.get("title", "") or ""), max_len=200).lower()
        snippet = self._normalize_text(str(raw.get("snippet", "") or ""), max_len=500).lower()
        query_terms = [term for term in re.split(r"\s+", query.lower()) if len(term) > 2]

        if strategy == "dive":
            if query_terms and not any(term in title or term in snippet for term in query_terms):
                return False, "dive_query_mismatch"
        elif strategy == "anchor":
            if query_terms and not any(term in text for term in query_terms):
                return False, "anchor_query_mismatch"
        elif strategy == "radar":
            if not any(hint in text for hint in _EVENT_HINTS + _COMPANY_HINTS + _CONTACT_HINTS) and len(text) < 40:
                return False, "radar_low_signal"

        return True, None

    def normalize_raw(self, raw: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(raw)
        normalized["url"] = self._normalize_url(str(raw.get("url", "") or ""))
        normalized["title"] = self._normalize_text(str(raw.get("title", "") or ""), max_len=200)
        normalized["snippet"] = self._normalize_text(str(raw.get("snippet", "") or ""), max_len=500)
        normalized["engine"] = self._normalize_text(str(raw.get("engine", "") or "searxng"), max_len=50)
        return normalized

    def classify(self, raw: dict[str, Any], query: str, strategy: str) -> dict[str, Any]:
        text = f"{raw.get('title', '')} {raw.get('snippet', '')} {query}".lower()
        domain = self._domain_from_url(str(raw.get("url", "") or ""))

        content_type = "general"
        if any(hint in text for hint in _EVENT_HINTS):
            content_type = "event"
        elif any(hint in text for hint in _COMPANY_HINTS):
            content_type = "company"
        elif any(hint in text for hint in _CONTACT_HINTS):
            content_type = "contact"

        source_kind = "site"
        if domain.endswith("linkedin.com") or domain.endswith("facebook.com"):
            source_kind = "social"
        elif domain.endswith("luma.com") or domain.endswith("lu.ma"):
            source_kind = "event_platform"
        elif domain.endswith("github.com"):
            source_kind = "repository"

        return {
            "content_type": content_type,
            "source_kind": source_kind,
            "strategy": strategy,
            "query_length": len(query.split()),
            "is_event_like": content_type == "event",
            "is_company_like": content_type == "company",
            "is_contact_like": content_type == "contact",
            "domain": domain,
        }

    def dedupe_key(self, raw: dict[str, Any]) -> str:
        url = self._normalize_url(str(raw.get("url", "") or ""))
        title = self._normalize_text(str(raw.get("title", "") or ""), max_len=120)
        domain = self._domain_from_url(url)
        return hashlib.sha1(f"{domain}|{url}|{title}".encode("utf-8")).hexdigest()

    def process(self, raw: dict[str, Any], query: str, strategy: str) -> ProcessingResult:
        accepted, reason = self.prefilter(raw, query, strategy)
        normalized = self.normalize_raw(raw)
        classification = self.classify(normalized, query, strategy)
        return ProcessingResult(
            accepted=accepted,
            prefilter_reason=reason,
            normalized=normalized,
            classification=classification,
            dedupe_key=self.dedupe_key(normalized),
        )

    @staticmethod
    def _normalize_text(value: str, max_len: int) -> str:
        cleaned = _WHITESPACE_RE.sub(" ", value).strip()
        return cleaned[:max_len]

    @staticmethod
    def _normalize_url(value: str) -> str:
        if not value:
            return ""
        parsed = urlparse(value.strip())
        scheme = parsed.scheme or "https"
        netloc = parsed.netloc.lower()
        path = parsed.path.rstrip("/")
        return urlunparse((scheme, netloc, path, "", "", ""))

    @staticmethod
    def _domain_from_url(value: str) -> str:
        if not value:
            return ""
        parsed = urlparse(value)
        return parsed.netloc.lower().removeprefix("www.")
