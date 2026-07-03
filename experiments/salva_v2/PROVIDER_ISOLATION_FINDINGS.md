# Provider Isolation Findings — locating the E10/E21/E21c failure layer

**Date:** 2026-07-03
**Status:** Root cause identified for 2 of 5 providers; 1 provider's failure mode
matches the E21c symptom description closely enough to be the leading
explanation, not proven with certainty against the original run's exact state.

## Method

Bypassed the full discovery pipeline (`core/controller.py`) entirely. Called
each retrieval provider's `.search()` directly, one query at a time, with a
2-second delay between every request (15 requests total across 3 queries ×
5 providers — deliberately small volume, not a stress test, per this card's
own guardrail and out of respect for public services' rate limits). Ran
*after* the three P1 prerequisite fixes landed (`ddgs` installed,
`_apply_live_probe` hard-degrade fixed, local SearXNG confirmed running) —
this is the first clean-environment read on provider health this project has
had.

Queries (reused from E21/E21c/E10 where possible, per the card's suggestion):
1. "CNCF founding member companies" (E21c)
2. "Naturehike camping gear DACH distributor" (E10/E21 theme)
3. "Taiwan AI hardware startups" (general sanity check, unrelated to any
   prior failing run, to distinguish "these two topics are just hard" from
   "the providers are broken")

Script: one-off diagnostic, not part of the pytest suite (this is an
observation task, not a regression test) — not committed as a repo script;
see this file for the full transcript.

## Results

| provider | Q1 (CNCF) | Q2 (Naturehike) | Q3 (Taiwan AI) | verdict |
|---|---:|---:|---:|---|
| `searxng` (local) | 5 results, **irrelevant** (typing-test sites) | 5 results, on-topic | 5 results, generic (Wikipedia/Britannica "Taiwan" pages, not AI-hardware-specific) | ⚠️ **unreliable, not broken** |
| `searxng_pool` (public mirrors) | 0 | 0 | 0 | ⚠️ degraded (cooldown-gated, not necessarily "down") |
| `ddgs` | 5 results, **all genuinely relevant** (Wikipedia CNCF page, cncf.io members page, GitHub charter) | 5 results, **all genuinely relevant** (naturehike.com store/wholesale pages) | 5 results, **all genuinely relevant** (Wikipedia AI-in-Taiwan, EE Times, PRNewswire) | ✅ **PASS — best provider by far** |
| `ddg_html` | 0 | 0 | 0 | ❌ **FAIL — completely non-functional** |
| `marginalia` | 5 results, on-topic (CNCF-adjacent blog/analysis pieces) | 0 (no coverage) | 5 results, on-topic (AI/semiconductor analysis blogs) | ⚠️ partial coverage gap, not a bug |

## Root-cause digging: why is `searxng` (local) inconsistent?

Q1's "typing-test websites" and a follow-up direct call both returned content
with zero semantic relation to the query. Isolated the cause by querying the
raw SearXNG JSON API directly (bypassing Salva's Python client entirely) with
the exact same engine bundle `SearXNGRetriever` uses (`google,bing,duckduckgo`,
one of three rotating bundles in `retrieval/sources/searxng.py::ENGINE_ROTATION`):

```
engines=google,bing,duckduckgo  -> 10 results, ALL irrelevant
  (a Chinese GPU benchmark article, an Italian Instagram tutorial, etc.)
```

Then tested each engine individually against the same query:

```
engines=google       -> 0 results
engines=bing          -> 3 results, ALL irrelevant (Japanese song lyrics site)
engines=duckduckgo     -> 0 results
```

**This is a raw SearXNG-instance/upstream-engine problem, not a Salva parsing
bug** — confirmed by querying SearXNG's own JSON API directly with curl,
completely outside any Salva code path. `google` and `duckduckgo` are
returning empty (likely blocked/rate-limited against this local instance —
common and expected for free public search engines hit by an unauthenticated
scraper). `bing` is worse: it's not empty, it returns **confident-looking but
completely unrelated content** — silently wrong, not a clean failure.

Because `SearXNGRetriever` rotates through 3 engine bundles
(`ENGINE_ROTATION`) across successive calls in the same process, and each
bundle includes at least one broken engine, **whether a given call returns
good or garbage results is essentially a coin flip determined by which
bundle the rotation lands on** — not a property of the query itself. Q2
(Naturehike) happened to land on a working combination; Q1 (CNCF) and the
follow-up call did not.

## Answering the card's core question: what caused E21c's "19 requests, zero
true positives, LinkedIn pages and unrelated blog posts"?

**Leading explanation, not proven with full certainty:** the `bing` engine
failure mode found above — silently returning unrelated, business-directory/
social-media-flavored content (in this test: gym franchise pages, Facebook,
Instagram profiles) rather than an empty result or a clean error — is a close
behavioral match to E21c's reported symptom (LinkedIn pages, unrelated blog
posts: same flavor of "generic web noise dressed up as a plausible-looking
result page"). At the time of E21/E21c (2026-06-12), this session's earlier
P1 diagnosis found no local SearXNG listening on port 8080 *as of this
session's start* (2026-07-03) — but that only proves the instance was down
*recently*, not that it was necessarily down on 2026-06-12; the container was
created 2026-05-07 with `restart: unless-stopped`, so it may well have been
running (and already engine-broken in this same way) during the actual E21c
run. **We cannot fully reconstruct E21c's exact provider-chain state in
hindsight** — this finding should be read as "a well-evidenced, mechanism-
matching candidate explanation," not a confirmed forensic reconstruction.

What we *can* say with confidence from this clean-environment test: **if
E21/E21c were re-run today, the default provider chain
(`retrieval/registry.py::_build_default_chain()`: searxng → whoogle → ddgs →
marginalia → searxng_pool → content_fetch) would reach `ddgs` after `searxng`
and get genuinely relevant results** — `ddgs` was completely unavailable
during the original E10/E21/E21c runs (confirmed in the `salva-p1-ddgs-
install-verify` card: missing from the `dev` extras group), so those runs
never had access to the one provider that performed perfectly in this test.

## Verdict

- **PASS**: `ddgs` — reliable, relevant results across all 3 diverse queries.
  This provider was simply never reachable during E10/E21/E21c.
- **FAIL**: `ddg_html` — 0/3, completely non-functional. Low remaining impact
  now that `ddgs` is available and ordered before it in the default chain,
  but still dead weight as a fallback.
- **UNRELIABLE, not cleanly broken**: `searxng` (local) — structurally works
  (non-empty, well-formed JSON) but its `google`/`duckduckgo` sub-engines
  return empty and `bing` returns confidently-wrong content, making result
  quality dependent on engine-rotation luck rather than the query itself.
- **DEGRADED, working as designed**: `searxng_pool` (public mirrors) — 0/3,
  most likely explained by this session's own earlier live-retrieval attempts
  (the stability-gating eval card, and this diagnostic's own local-SearXNG
  calls) having already tripped the 4-hour cooldown gate
  (`retrieval/health.py`, `_MAX_TRIES_PER_QUERY=2` in
  `retrieval/sources/searxng_pool.py`) on some of the 5 default public
  instances. Did not re-test with a longer gap to confirm, to avoid burning
  more request budget against public services just to prove this.
- **PARTIAL COVERAGE, not a bug**: `marginalia` — 2/3 queries got relevant
  results; the Naturehike e-commerce/distributor query got 0, consistent with
  Marginalia's documented bias toward independent/technical sites over
  commercial/e-commerce content (`retrieval/registry.py`'s own
  `ProviderDescriptor` description says as much).

## What this does NOT prove

- Whether the `searxng` local instance's engine breakage
  (google/duckduckgo empty, bing wrong) is a transient issue with this
  specific instance/moment, or a persistent misconfiguration. Not
  investigated further — fixing SearXNG's own engine configuration is
  outside this card's scope (guardrail: no changes to `retrieval/sources/*.py`
  or `registry.py`, this is an observation-only card).
- Whether re-running E21/E21c today (with `ddgs` now available) would
  actually reproduce E10-style dogfood recall — that's exactly what the next
  card (`salva-p2-task-set-design` → `salva-p2-experiment-protocol` →
  `salva-p3-execute-arms`) is for, at a larger and more rigorous scale than
  this 3-query diagnostic.
- The exact historical state of the local SearXNG instance during the
  original E10/E21/E21c runs (2026-06-08/06-12) — the "leading explanation"
  above is evidence-based but not a forensic reconstruction of a system state
  that no longer exists to inspect directly.
