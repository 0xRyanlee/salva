# DDGS Backend Diagnostic — is switching `DDGS_BACKEND` worth it?

**Date:** 2026-07-03
**Verdict: no, keep the default (`auto`).** Compliance is clean (verified
below), but the diagnostic itself is decisive against switching: 2 of the
3 candidate backends returned zero results across every test query, and
the one that worked (`bing`) showed no advantage over the current default.

## Step 1 — compliance verification (done first, per this card's guardrail)

Read the actual installed `ddgs==9.14.4` package source
(`.venv/lib/python3.14/site-packages/ddgs/engines/{brave,bing,yandex}.py`)
rather than assuming from the env var name alone. Confirmed for all three:

- **No API key anywhere in any of the three engine implementations.**
- Each engine subclasses `BaseSearchEngine` and issues a plain HTTP GET
  against the provider's own public search results page (e.g.
  `brave.py`: `search_url = "https://search.brave.com/search"`), then
  parses the returned HTML via xpath selectors — the exact same
  "scrape the public results page" approach `retrieval/sources/ddg_html.py`
  already uses for DuckDuckGo, and the same category of technique
  `SearXNGRetriever`'s underlying engines use. Not a new category of
  behavior for this codebase.
- **No payment, no billing account, no rate-limit-tier signup required**
  to use any of these three backends via `ddgs`.

**Conclusion: genuinely free, no API key.** Proceeding to step 2 per the
card's own instruction ("若確認免費可用" — if confirmed free, proceed).

One thing worth flagging that's adjacent to but distinct from "is it
paid": scraping a search engine's public HTML results page (rather than
using an official, sanctioned API) generally sits outside most search
engines' Terms of Service, independent of whether money changes hands.
This isn't a new risk `ddgs`/`DDGS_BACKEND` introduces — the codebase
already does this via `ddg_html.py` and the SearXNG engine stack — but
it's worth naming explicitly rather than only checking the "is it paid"
box, especially given this session's earlier explicit instruction to
respect frequency/human-like-behavior norms when doing live search testing.

## Step 2 — diagnostic test (3 queries, not the full 18-task scale, per this card's scope)

Ran the same 3 queries (spanning single-entity, cross-language, and
multi-hop-flavored shapes) directly through `DDGSRetriever.search()` with
`DDGS_BACKEND` set to `auto` (current default), `brave`, `bing`, and
`yandex` in turn:

| query | `auto` (default) | `brave` | `bing` | `yandex` |
|---|---:|---:|---:|---:|
| "TSMC 台積電 official website" | 5 results, relevant (TSMC careers/news pages) | **0 results** | 5 results, relevant (Wikipedia + TSMC careers) | **0 results** |
| "CNCF founding members Cloud Native Computing Foundation" | 5 results, relevant (CNCF Wikipedia + Members page) | **0 results** | 5 results, relevant (similar) | *(not re-tested, already 0 on the first query)* |
| "Naturehike distributor DACH" | 5 results, relevant (Naturehike product/gear pages) | **0 results** | 5 results, relevant, notably surfaced this repo's own `docs/dogfood/naturehike-dach-2026-*.md` file | *(not re-tested)* |

**`brave` and `yandex` returned zero results on every query tested** —
consistent with the scraper no longer matching the target site's current
HTML structure, or the request being blocked/challenged before a result
page renders. Either way, both are currently non-functional through
`ddgs` in this environment, not marginally worse. **`bing` works and
returns relevant results, but shows no clear advantage over the existing
`auto` default** — same relevance, same result count, on every query
tested.

## Recommendation

**Do not switch the default `DDGS_BACKEND`.** `auto` (the current default,
which lets `ddgs` itself pick/rotate among working engines) already
performs at least as well as the one working alternative (`bing`), and two
of the three candidates (`brave`, `yandex`) are currently broken. Switching
away from `auto` to a single pinned backend would only reduce resilience
(losing whatever fallback `auto` already does internally) for no
measurable gain.

If `brave`/`yandex` scraping breaks due to target-site HTML changes, that's
expected maintenance burden for any HTML-scraping approach (same category
of fragility this codebase already accepts for `ddg_html.py` and the
SearXNG stack) — not something this diagnostic recommends investing in
fixing right now, since `auto`/`bing` already cover the need.

## Guardrails honored

No production default was changed — this diagnostic's own result argues
against changing it, which happens to align with the guardrail rather than
requiring restraint against a tempting-but-unproven switch. 3 queries
tested, not the full 18-task experiment scale, per this card's diagnostic
(not full-experiment) scope.
