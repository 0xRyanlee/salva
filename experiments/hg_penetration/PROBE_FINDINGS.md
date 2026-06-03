# Data-acquisition probe findings (2026-06-03)

**Question (concern B, the "data death-valley" risk):** can public sources
reliably yield equity facts for real companies, per jurisdiction?

**Method:** used Salva-acquisition proxies (web search to locate sources + direct
public-API/web fetch) on real companies; `probe_sec.py` is the reproducible
fully-open anchor (`python -m experiments.hg_penetration.probe_sec`).

## Verdict: the death-valley is NOT uniform — it is jurisdiction × company-type specific

| Jurisdiction / type | Access | Method | Reliability | Legal | Friction |
|---|---|---|---|---|---|
| **US** (any reporting co.) | ✅ trivial | `data.sec.gov` + `efts.sec.gov` free JSON, no auth/captcha | high | public disclosure | none |
| **UK** (any co.) | ✅ easy | Companies House API (PSC = beneficial ownership), free key | high | public registry | API key |
| **TW listed** | ✅ accessible | MOPS 公開資訊觀測站 (董監事/大股東持股) | high | public disclosure | form-driven web (scrape) |
| **CN listed** | ✅ accessible | 巨潮 cninfo 定期報告 (十大股东/流通股东) · Tushare `top10_holders` | high | public disclosure | PDF/API parse |
| **TW private** | ⚠️ partial | 商工登記 (負責人/董監事/部分股東) · TDCC | medium | **partial** — full roster not public (§210) | legal ceiling |
| **CN private (registry)** | ⚠️ hard | gsxt 股东/出资 exists but heavy anti-bot/captcha; 天眼查/企查查 paywalled | medium | public but gated | anti-bot / paid |

### Proven (real data, this probe)
- **Apple (SEC):** 1000 recent filings → **23 SC 13D/G** (5%+ owners), **587 Form 4** (insider), **11 DEF 14A** (beneficial-ownership table). Free, structured, no captcha.
- **SEC full-text `"acting in concert"` + SC 13D → 2074 filings.** The exact n-ary
  phenomenon the penetration experiment demonstrated (concert-party control) is a
  **real, documented, searchable fact** in US filings; SC 13D *group* filings list
  multiple reporting persons = a literal n-ary concert hyperedge.

## Implications

1. **Concern B is largely de-risked for LISTED companies** across US/UK/TW/CN —
   equity facts are public and (mostly) programmatically accessible.
2. **Friction concentrates on:** CN/TW **private** companies (registry anti-bot or
   legally restricted) and cross-source **entity resolution** (reuse Nomenklatura).
3. **Beachhead refinement → start with LISTED-company equity intelligence.** Clean,
   accessible, and the hypergraph thesis meets real data here (SEC concert-group
   filings). Expand to private/registry where friction is higher, later.
4. The Jurisdiction Source Registry's `access` / `reliability` / `legal_availability`
   now carry **probe-verified** values (see table) — the seed is grounded, not guessed.

## Next increments
1. Pull a real SEC SC 13D **group** filing → build a real n-ary concert hyperedge
   end-to-end (acquisition → extraction → hyperedge → penetration) on a real company.
2. Wire `source_attempts` → re-rank the registry (prove routing *learns*).
3. TW listed via MOPS data files; CN listed via cninfo/Tushare.
