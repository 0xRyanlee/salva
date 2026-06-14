"""E24 — Sitemap-first Discovery Benchmark (VP24).

Hypothesis (VP24):
  SitemapRetriever can reliably extract entity-directory candidate URLs from a
  domain's sitemap.xml, providing Tier-1 source-direct discovery without
  requiring a search engine query.

Design:
  S1 — Mock: synthetic robots.txt + sitemap.xml with known directory URLs.
       Verifies URL extraction logic without network dependency.

  S2 — Live (optional): real public domain with known sitemap structure.
       Verifies the full HTTP stack end-to-end.
       Skipped if network unavailable.

Pass criteria:
  P1: S1 mock — ≥3 directory-like URLs extracted from synthetic sitemap
  P2: S1 mock — all extracted URLs contain at least one _DIRECTORY_KEYWORDS token
  P3: S2 live — ≥1 URL extracted from real domain sitemap (if network available)

Run:
    python -m experiments.computex_2026.e24_sitemap_discovery
"""
from __future__ import annotations

import textwrap
import time
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from salva_core.schemas import RetrievalPolicy


# ---------------------------------------------------------------------------
# Fixture data — synthetic sitemap
# ---------------------------------------------------------------------------

_ROBOTS_TXT = textwrap.dedent("""\
    User-agent: *
    Disallow: /private/

    Sitemap: https://example-corp.test/sitemap.xml
""")

_SITEMAP_XML = textwrap.dedent("""\
    <?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://example-corp.test/</loc></url>
      <url><loc>https://example-corp.test/about</loc></url>
      <url><loc>https://example-corp.test/members/google</loc></url>
      <url><loc>https://example-corp.test/members/microsoft</loc></url>
      <url><loc>https://example-corp.test/members/amazon</loc></url>
      <url><loc>https://example-corp.test/sponsors/platinum/intel</loc></url>
      <url><loc>https://example-corp.test/sponsors/gold/ibm</loc></url>
      <url><loc>https://example-corp.test/partner-network/asia</loc></url>
      <url><loc>https://example-corp.test/distributor-list</loc></url>
      <url><loc>https://example-corp.test/blog/post-1</loc></url>
      <url><loc>https://example-corp.test/blog/post-2</loc></url>
      <url><loc>https://example-corp.test/careers</loc></url>
    </urlset>
""")

# Minimum number of directory URLs expected from the mock sitemap
_EXPECTED_MIN = 3


# ---------------------------------------------------------------------------
# Scenario results
# ---------------------------------------------------------------------------

@dataclass
class ScenarioResult:
    name: str
    passed: bool
    found_urls: list[str]
    details: str
    elapsed_ms: float


# ---------------------------------------------------------------------------
# S1 — Mock scenario
# ---------------------------------------------------------------------------

def run_s1() -> ScenarioResult:
    from retrieval.sources.sitemap import SitemapRetriever, _DIRECTORY_KEYWORDS

    t0 = time.monotonic()

    _url_map: dict[str, bytes] = {
        "https://example-corp.test/robots.txt": _ROBOTS_TXT.encode(),
        "https://example-corp.test/sitemap.xml": _SITEMAP_XML.encode(),
    }

    def _mock_http_get(url: str, timeout: float = 10.0) -> bytes:
        if url in _url_map:
            return _url_map[url]
        raise OSError(f"Mock: no fixture for {url}")

    with patch("retrieval.sources.sitemap.http_get", side_effect=_mock_http_get):
        retriever = SitemapRetriever(policy=RetrievalPolicy())
        results = retriever.discover_domain("https://example-corp.test/", n=20)

    found_urls = [r["url"] for r in results]
    # All returned URLs must contain at least one keyword from the actual
    # _DIRECTORY_KEYWORDS set used by SitemapRetriever — no spurious URLs
    dir_keyword_hit = [
        u for u in found_urls
        if any(kw in u.lower() for kw in _DIRECTORY_KEYWORDS)
    ]

    p1 = len(found_urls) >= _EXPECTED_MIN
    p2 = len(dir_keyword_hit) == len(found_urls)
    passed = p1 and p2

    elapsed = (time.monotonic() - t0) * 1000
    details = (
        f"found={len(found_urls)} (want ≥{_EXPECTED_MIN}) | "
        f"keyword_match={len(dir_keyword_hit)}/{len(found_urls)}"
    )
    return ScenarioResult("S1 mock sitemap", passed, found_urls, details, elapsed)


# ---------------------------------------------------------------------------
# S2 — Live scenario (linux.com has a public sitemap with known structure)
# ---------------------------------------------------------------------------

_LIVE_DOMAIN = "https://www.linuxfoundation.org"
_LIVE_MIN_RESULTS = 1


def _check_network() -> bool:
    try:
        urllib.request.urlopen("https://www.linuxfoundation.org", timeout=5)
        return True
    except Exception:
        return False


def run_s2() -> ScenarioResult | None:
    from retrieval.sources.sitemap import SitemapRetriever

    t0 = time.monotonic()
    retriever = SitemapRetriever(policy=RetrievalPolicy())
    try:
        results = retriever.discover_domain(_LIVE_DOMAIN, n=20)
    except Exception as exc:
        elapsed = (time.monotonic() - t0) * 1000
        return ScenarioResult(
            "S2 live sitemap", False, [],
            f"Exception: {exc}", elapsed,
        )

    found_urls = [r["url"] for r in results]
    passed = len(found_urls) >= _LIVE_MIN_RESULTS
    elapsed = (time.monotonic() - t0) * 1000
    details = f"found={len(found_urls)} from {_LIVE_DOMAIN} (want ≥{_LIVE_MIN_RESULTS})"
    return ScenarioResult("S2 live sitemap", passed, found_urls, details, elapsed)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("E24 — Sitemap-first Discovery Benchmark")
    print()

    results: list[ScenarioResult] = []

    # S1: always run (mock)
    print("  Running S1 (mock sitemap)…")
    r1 = run_s1()
    status = "✓ PASS" if r1.passed else "✗ FAIL"
    print(f"  {status}  {r1.name}")
    print(f"         {r1.details}  ({r1.elapsed_ms:.1f}ms)")
    if r1.found_urls:
        for u in r1.found_urls[:6]:
            print(f"    → {u}")
    results.append(r1)
    print()

    # S2: only run if network available
    has_network = _check_network()
    if has_network:
        print(f"  Running S2 (live: {_LIVE_DOMAIN})…")
        r2 = run_s2()
        if r2:
            status2 = "✓ PASS" if r2.passed else "✗ FAIL"
            print(f"  {status2}  {r2.name}")
            print(f"         {r2.details}  ({r2.elapsed_ms:.1f}ms)")
            if r2.found_urls:
                for u in r2.found_urls[:5]:
                    print(f"    → {u}")
            results.append(r2)
    else:
        print("  ⚠ S2 skipped — network unavailable")

    print()
    passed_n = sum(1 for r in results if r.passed)
    total = len(results)
    overall = "PASS" if r1.passed else "FAIL"  # P1/P2 are the gating criteria
    print(f"  Overall: {passed_n}/{total}  →  {overall}")

    # Write findings
    path = Path(__file__).parent / "E24_FINDINGS.md"
    with open(path, "w", encoding="utf-8") as f:
        f.write("# E24 — Sitemap-first Discovery Benchmark\n\n")
        f.write(f"**Date:** {datetime.now(UTC).strftime('%Y-%m-%d')}\n\n")
        f.write("## Results\n\n")
        f.write("| Scenario | Result | Details |\n")
        f.write("|---|---|---|\n")
        for r in results:
            v = "✓ PASS" if r.passed else "✗ FAIL"
            f.write(f"| {r.name} | {v} | {r.details} |\n")
        f.write(f"\n**Verdict: {overall}**\n\n")
        f.write("## S1 URLs extracted\n\n")
        for u in r1.found_urls:
            f.write(f"- {u}\n")
        if len(results) > 1 and results[1].found_urls:
            f.write("\n## S2 URLs extracted\n\n")
            for u in results[1].found_urls[:10]:
                f.write(f"- {u}\n")
    print(f"\n  Findings written → {path}")


if __name__ == "__main__":
    main()
