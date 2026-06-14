"""Tests for RSSRetriever — feed detection and parsing (RSS 2.0 + Atom)."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from retrieval.sources.rss import RSSRetriever
from salva_core.schemas import RetrievalPolicy

_RSS_FEED = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Example News</title>
    <item>
      <title>ACME Corp joins Example Foundation</title>
      <link>https://example.com/news/acme-joins</link>
      <description>ACME Corp announced membership</description>
    </item>
    <item>
      <title>Beta Ltd becomes platinum member</title>
      <link>https://example.com/news/beta-platinum</link>
      <description>Beta Ltd upgrades to platinum</description>
    </item>
  </channel>
</rss>"""

_ATOM_FEED = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Foundation Updates</title>
  <entry>
    <title>Gamma Inc becomes sponsor</title>
    <link href="https://example.com/updates/gamma-sponsor"/>
    <summary>Gamma Inc announced their sponsorship</summary>
  </entry>
  <entry>
    <title>Delta Corp member announcement</title>
    <link href="https://example.com/updates/delta-member"/>
    <summary>Delta Corp joins as member</summary>
  </entry>
</feed>"""


def _retriever() -> RSSRetriever:
    return RSSRetriever(RetrievalPolicy())


def test_rss_fetch_returns_entries() -> None:
    def _http(url, **kw):
        if "/feed" in url:
            return _RSS_FEED
        raise OSError("not found")
    with patch("retrieval.sources.rss.http_get", side_effect=_http):
        r = _retriever()
        entries = r.fetch_feed("https://example.com")
    assert len(entries) == 2
    assert entries[0]["title"] == "ACME Corp joins Example Foundation"
    assert entries[0]["url"] == "https://example.com/news/acme-joins"


def test_atom_feed_parsed() -> None:
    def _http(url, **kw):
        if "/feed" in url:
            return _ATOM_FEED
        raise OSError("not found")
    with patch("retrieval.sources.rss.http_get", side_effect=_http):
        r = _retriever()
        entries = r.fetch_feed("https://example.com")
    assert len(entries) == 2
    assert "Gamma Inc" in entries[0]["title"]
    assert entries[0]["engine"] == "rss_atom"


def test_no_feed_returns_empty() -> None:
    with patch("retrieval.sources.rss.http_get", side_effect=OSError("404")):
        r = _retriever()
        entries = r.fetch_feed("https://nofeed.example.com")
    assert entries == []


def test_entries_have_required_fields() -> None:
    def _http(url, **kw):
        if "/feed" in url:
            return _RSS_FEED
        raise OSError()
    with patch("retrieval.sources.rss.http_get", side_effect=_http):
        r = _retriever()
        entries = r.fetch_feed("https://example.com")
    for entry in entries:
        assert "title" in entry
        assert "url" in entry
        assert "snippet" in entry


def test_n_limit_respected() -> None:
    def _http(url, **kw):
        if "/feed" in url:
            return _RSS_FEED
        raise OSError()
    with patch("retrieval.sources.rss.http_get", side_effect=_http):
        r = _retriever()
        entries = r.fetch_feed("https://example.com", n=1)
    assert len(entries) <= 1


def test_malformed_feed_returns_empty() -> None:
    def _http(url, **kw):
        if "/feed" in url:
            return b"<rss><channel><item>broken"
        raise OSError()
    with patch("retrieval.sources.rss.http_get", side_effect=_http):
        r = _retriever()
        entries = r.fetch_feed("https://example.com")
    assert isinstance(entries, list)


def test_search_method_returns_empty() -> None:
    r = _retriever()
    assert r.search("any query") == []
