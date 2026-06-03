"""Data-acquisition probe: can a public source reliably yield equity facts?

Hits SEC EDGAR's public JSON endpoints (no auth, no captcha, free) for a given
company and reports how many ownership-bearing filings exist. This is the
"fully-open jurisdiction" anchor of the feasibility map — proves the
acquisition→location path works end-to-end on REAL data.

    python -m experiments.hg_penetration.probe_sec            # Apple
    python -m experiments.hg_penetration.probe_sec 0000789019 # MSFT

SEC requires a descriptive User-Agent.
"""
from __future__ import annotations

import collections
import json
import sys
import urllib.request

UA = "Salva Research Probe ryan910814@gmail.com"


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip, deflate"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = r.read()
    if r.headers.get("Content-Encoding") == "gzip":
        import gzip
        data = gzip.decompress(data)
    return data


def probe_company(cik: str = "0000320193") -> dict:
    cik = cik.zfill(10)
    sub = json.loads(_get(f"https://data.sec.gov/submissions/CIK{cik}.json"))
    forms = collections.Counter(sub["filings"]["recent"]["form"])
    return {
        "company": sub.get("name"),
        "cik": cik,
        "recent_filings": sum(forms.values()),
        "sc_13d_g_5pct_owners": sum(v for k, v in forms.items() if k.startswith("SC 13")),
        "form_4_insider": forms.get("4", 0),
        "def_14a_ownership_table": forms.get("DEF 14A", 0),
    }


def probe_concert_filings() -> int:
    """Full-text search: how many SC 13D filings mention 'acting in concert'?"""
    url = 'https://efts.sec.gov/LATEST/search-index?q=%22acting+in+concert%22&forms=SC+13D'
    return int(json.loads(_get(url))["hits"]["total"]["value"])


def main() -> None:
    cik = sys.argv[1] if len(sys.argv) > 1 else "0000320193"
    try:
        c = probe_company(cik)
        concert = probe_concert_filings()
    except Exception as exc:  # network / SEC unavailable
        print(f"[probe] SEC unreachable in this environment: {exc}")
        return
    print(f"company: {c['company']} (CIK {c['cik']})")
    print(f"  recent filings:        {c['recent_filings']}")
    print(f"  SC 13D/G (5%+ owners): {c['sc_13d_g_5pct_owners']}")
    print(f"  Form 4 (insider tx):   {c['form_4_insider']}")
    print(f"  DEF 14A (ownership):   {c['def_14a_ownership_table']}")
    print(f"SEC full-text 'acting in concert' + SC 13D: {concert} filings")
    print("→ US equity facts (incl. n-ary concert-group filings) are publicly and")
    print("  programmatically accessible, free, no auth, no captcha.")


if __name__ == "__main__":
    main()
