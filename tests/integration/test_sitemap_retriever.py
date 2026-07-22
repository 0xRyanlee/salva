"""Tests for SitemapRetriever — robots.txt → sitemap.xml → directory URL candidates."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from retrieval.sources.sitemap import SitemapRetriever
from salva_core.schemas import RetrievalPolicy

_ROBOTS = b"""
User-agent: *
Disallow: /private/

Sitemap: https://example.com/sitemap.xml
"""

_SITEMAP = b"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/partners/germany</loc></url>
  <url><loc>https://example.com/distributors/europe</loc></url>
  <url><loc>https://example.com/wholesale/catalog</loc></url>
  <url><loc>https://example.com/blog/post-1</loc></url>
  <url><loc>https://example.com/about-us</loc></url>
  <url><loc>https://example.com/members/platinum</loc></url>
</urlset>
"""

_SITEMAP_INDEX = b"""<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://example.com/sitemap-pages.xml</loc></sitemap>
</sitemapindex>
"""


def _retriever() -> SitemapRetriever:
    return SitemapRetriever(RetrievalPolicy())


def _mock_http(responses: dict[str, bytes]):
    def _get(url: str, **kw) -> bytes:
        for pattern, content in responses.items():
            if pattern in url:
                return content
        raise OSError(f"not mocked: {url}")
    return patch("retrieval.sources.sitemap.http_get", side_effect=_get)


def test_discover_finds_directory_urls_via_robots() -> None:
    responses = {
        "robots.txt": _ROBOTS,
        "sitemap.xml": _SITEMAP,
    }
    with _mock_http(responses):
        r = _retriever()
        results = r.discover_domain("https://example.com", n=10)
    urls = [res["url"] for res in results]
    assert any("partners" in u or "distributors" in u or "wholesale" in u or "members" in u for u in urls)


def test_discover_filters_out_blog_urls() -> None:
    responses = {
        "robots.txt": _ROBOTS,
        "sitemap.xml": _SITEMAP,
    }
    with _mock_http(responses):
        r = _retriever()
        results = r.discover_domain("https://example.com", n=10)
    urls = [res["url"] for res in results]
    assert "https://example.com/blog/post-1" not in urls


def test_discover_returns_empty_when_no_sitemap() -> None:
    def _fail(url, **kw):
        raise OSError("no sitemap")
    with patch("retrieval.sources.sitemap.http_get", side_effect=_fail):
        r = _retriever()
        results = r.discover_domain("https://example.com")
    assert results == []


def test_discover_follows_sitemap_index() -> None:
    _sub_sitemap = b"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/dealer/list</loc></url>
</urlset>"""
    responses = {
        "robots.txt": b"Sitemap: https://example.com/sitemap_index.xml\n",
        "sitemap_index.xml": _SITEMAP_INDEX,
        "sitemap-pages.xml": _sub_sitemap,
    }
    with _mock_http(responses):
        r = _retriever()
        results = r.discover_domain("https://example.com", n=5)
    urls = [res["url"] for res in results]
    assert "https://example.com/dealer/list" in urls


def test_discover_result_has_required_fields() -> None:
    responses = {
        "robots.txt": _ROBOTS,
        "sitemap.xml": _SITEMAP,
    }
    with _mock_http(responses):
        r = _retriever()
        results = r.discover_domain("https://example.com", n=3)
    if results:
        res = results[0]
        assert "title" in res
        assert "url" in res
        assert "snippet" in res
        assert res["engine"] == "sitemap"


def test_discover_respects_n_limit() -> None:
    responses = {
        "robots.txt": _ROBOTS,
        "sitemap.xml": _SITEMAP,
    }
    with _mock_http(responses):
        r = _retriever()
        results = r.discover_domain("https://example.com", n=2)
    assert len(results) <= 2
