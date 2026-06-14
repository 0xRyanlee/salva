"""Real acquisition from SEC EDGAR: turn a SC 13D group filing into an n-ary
concert hyperedge, end-to-end, on a real listed company.

A SC 13D filed by multiple reporting persons IS a §13(d)(3) "group" — a real,
legally-defined acting-in-concert relation. We extract it from SEC's structured
filing metadata (display_names + ciks), not fragile HTML parsing.
"""
from __future__ import annotations

import gzip
import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

from experiments.hg_penetration.routing import SourceAttempt
from experiments.hg_penetration.store import HypergraphStore

UA = "Salva Research Probe ryan910814@gmail.com"


@dataclass
class Filing:
    accession: str
    subject: str
    reporting_persons: list[str]
    ciks: list[str]
    date: str
    url: str
    extra: dict = field(default_factory=dict)


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=25) as r:
        data = r.read()
        enc = r.headers.get("Content-Encoding")
    return gzip.decompress(data) if enc == "gzip" else data


def _clean_name(display: str) -> str:
    # "BlueMountain Capital Management, LLC  (CIK 0001427430)" -> "BlueMountain Capital Management, LLC"
    return re.split(r"\s*\(CIK", display)[0].strip()


def _extract_reporting_persons(url: str) -> list[str]:
    """SC 13D cover pages: 'NAME OF REPORTING PERSON ...'. Multiple = a group."""
    try:
        txt = _get(url).decode("utf-8", "ignore")
    except Exception:
        return []
    import html
    txt = html.unescape(re.sub(r"<[^>]+>", " ", txt)).replace("\xa0", " ")
    raw = re.findall(
        r"NAME[S]?\s+OF\s+REPORTING\s+PERSON[S]?\s*[:.]?\s*\n?\s*(.{2,80}?)\s*(?:\n|I\.?R\.?S\.?|S\.?S\.? OR)",
        txt, re.I,
    )
    seen: dict[str, str] = {}
    for r in raw:
        name = re.sub(r"\s+", " ", r).strip().rstrip(".,")
        name = re.sub(r"^[A-Z]\s+(?=[A-Z][a-z])", "", name)  # strip leading checkbox-column artifact ("S BlueMountain")
        name = re.sub(r"^\W+", "", name)
        key = name.lower()
        if len(name) >= 4 and not key.startswith(("see ", "this ", "page", "name")):
            seen.setdefault(key, name)
    return list(seen.values())


def _doc_url(accession: str, cik: str, fname: str) -> str:
    return f"https://www.sec.gov/Archives/edgar/data/{cik.lstrip('0') or '0'}/{accession.replace('-', '')}/{fname}"


def find_group_filing(query: str = "members of a group", scan: int = 6) -> Filing | None:
    """Scan SC 13D candidates, read each cover, pick the one with the most reporting persons."""
    q = urllib.parse.quote(f'"{query}"')
    url = f"https://efts.sec.gov/LATEST/search-index?q={q}&forms=SC+13D"
    hits = json.loads(_get(url))["hits"]["hits"]

    best: Filing | None = None
    for h in hits[:scan]:
        s = h["_source"]
        names = [_clean_name(n) for n in s.get("display_names", [])]
        if not names:
            continue
        subject = names[0]
        accession, _, fname = h["_id"].partition(":")
        ciks = s.get("ciks") or ["0"]
        doc = _doc_url(accession, ciks[0], fname)
        persons = _extract_reporting_persons(doc) or names[1:]
        f = Filing(
            accession=accession, subject=subject, reporting_persons=persons,
            ciks=ciks, date=s.get("file_date", ""), url=doc,
        )
        if best is None or len(f.reporting_persons) > len(best.reporting_persons):
            best = f
        if best and len(best.reporting_persons) >= 3:
            break
    return best


def _nid(name: str) -> str:
    return "ent:" + re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:48]


def build_hyperedge(store: HypergraphStore, f: Filing) -> str:
    subj = _nid(f.subject)
    store.add_node(subj, "company", f.subject)
    edge = f"e_group_{f.accession}"
    # A multi-person SC 13D is a §13(d)(3) group = acting in concert by law.
    store.add_hyperedge(edge, "control", acting_in_concert=True,
                        basis="SC 13D §13(d)(3) group", date=f.date)
    store.add_incidence(edge, subj, role="controlled", order_index=0)
    for i, person in enumerate(f.reporting_persons, start=1):
        pid = _nid(person)
        store.add_node(pid, "org", person)
        store.add_incidence(edge, pid, role="controller", order_index=i)
    store.add_evidence(edge, "SEC EDGAR", "US", "public_disclosure", url=f.url,
                       snippet=f"SC 13D group filing {f.accession}")
    store.conn.commit()
    return edge


def acquire(store: HypergraphStore, query: str = "members of a group") -> tuple[Filing | None, SourceAttempt]:
    try:
        f = find_group_filing(query)
    except Exception:
        return None, SourceAttempt("US", "equity", "SEC EDGAR", hit=False, result_count=0)
    if f is None:
        return None, SourceAttempt("US", "equity", "SEC EDGAR", hit=False, result_count=0)
    build_hyperedge(store, f)
    return f, SourceAttempt("US", "equity", "SEC EDGAR", hit=True, result_count=len(f.reporting_persons) + 1)
