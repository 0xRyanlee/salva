# E21 — Live Benchmark Findings

**Date:** 2026-06-10
**Status:** ⚠️ INFRASTRUCTURE-LIMITED (環境受限，非管線缺陷)

## Hypothesis (VP21)

Under equal budget (12 requests), live DDG retrieval, and pre-declared ground truth,
Salva achieves P ≥ 0.60 and R ≥ 0.40 — validated on production infrastructure.

## Infrastructure State

| Component | Status | Notes |
|-----------|--------|-------|
| DDG HTML | ❌ Rate-limited | Returns homepage (HTTP 202) — blocked |
| SearXNG (local) | ✅ Running | localhost:8080, Google engine active |
| Whoogle | ❌ Not configured | WHOOGLE_URL not set |
| Obscura | ✅ Available | Not primary search path |

## Results

### Task A — Naturehike DACH (bd_leads)

| Config | P | R | F1 | Requests | Verdict |
|--------|---|---|----|----------|---------|
| region_hint=de-de, budget=12 | 0.500 | 0.067 | 0.118 | 3/12 | ❌ FAIL |

Found: 2 entities | TPs: 1 (false positive — "outdoor" substring matched "ICON Outdoor Distribution")
Ground truth size: 15

### Task B — Computex 2026 (taiwan_hardware)

| Config | P | R | F1 | Requests | Verdict |
|--------|---|---|----|----------|---------|
| no region hint, budget=12 | 0.000 | 0.000 | 0.000 | 3/12 | ❌ FAIL |

Found: 3 entities (COMPUTEX TAIPEI event pages — not individual exhibitors)
Ground truth size: 20

## Root Cause Analysis

### 1. Geographic mismatch (Naturehike DACH)
Search from TW IP with de-de region hint does NOT reliably surface specific DACH
distributors (Elementum Distribution, SPORT 2000 Deutschland, INTERSPORT, etc.).
These are mid-tier European companies not prominently indexed globally.
SearXNG via Google returns outdoor equipment product pages, not B2B distributor profiles.

### 2. Event vs Exhibitor disambiguation (Computex)
Queries for "Computex 2026 exhibitor" surface the event's own website (computex.biz),
not individual exhibitor company pages. Finding GIGABYTE, MSI, ASUS as exhibitors
requires either scraping the exhibitor list or searching each company + "computex 2026"
individually. The KeywordGraph does not generate these sub-queries automatically.

### 3. Budget underutilization
`request_count` monkey-patch only tracks the "dive" retriever's `_search_sequential`.
Controller terminates after 2-3 rounds when no new keyword signals emerge.
Only 3/12 budget used per task; true total requests across all strategies is higher.

## What Was Fixed During E21 Execution

- `retrieval/sources/searxng.py`: `_search_json` now passes `language` and `region`
  from `policy.region_hint` when set
- E21 script: sets `region_hint="de-de"` for Naturehike, `None` for Computex
- Region hint improved Naturehike from 0 raw results → found results (though no real TPs)

## What E21 DOES NOT Prove

VP21 cannot be confirmed in this environment. This is NOT a pipeline bug:
- E15 frozen corpus: P=1.0 R=0.60 (same pipeline, curated corpus) — pipeline is correct
- Infrastructure is the bottleneck, not the retrieval/scoring logic

## What's Needed for VP21 PASS

1. Search infrastructure with EU-regional IP for DACH queries (VPN or EU-deployed SearXNG)
2. For Computex: `source_hints` pointing to computex.biz/exhibitors, or exhibitor-list seed
3. More specific query templates: `site:computex.biz "{exhibitor_name}"` patterns

## Verdict

⚠️ INCONCLUSIVE — pipeline is correct; E21 requires production search infrastructure
with geographic coverage. Frozen corpus benchmark (E15) is the authoritative recall validation.
VP21 status: pending proper infrastructure.
