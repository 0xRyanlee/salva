# Obscura Browser Source — Candidate-Pool Contribution Eval

Board card: `salva-p7-obscura-browser-source`.

## Question

Does `ObscuraBrowserRetriever` (`retrieval/sources/obscura.py`), registered
in `retrieval/registry.py` as a JS-rendering content-fetch source, contribute
candidates the accumulate+rerank pipeline's other sources (`ddgs`) miss, when
plugged into the offline experiment harness alongside
`confidence_rebuild_experiment.py` / `rerank_fullscale_validation.py`?

## Verdict: could not be evaluated — sandbox network blocks the discovery step it depends on

This is an environment limitation, not a finding about the provider's
real-world value. No comparison numbers are reported below because none
could be produced honestly; see "What would be needed to actually run this"
for the conditions under which this eval should be re-attempted.

## What was checked

**1. The obscura binary itself works in this sandbox.** It is installed
(`/Users/galaxyorion/.local/bin/obscura`, auto-detected via `shutil.which`)
and can fetch + JS-render arbitrary URLs when given one directly:

```
$ obscura fetch https://example.com
Fetching https://example.com...
Page loaded: https://example.com/ - "Example Domain"
<!DOCTYPE html>...
```

**2. `ObscuraBrowserRetriever.search()` cannot produce any candidates in this
sandbox**, because its URL-discovery step is a raw HTTP POST to
`https://html.duckduckgo.com/html/` (`_search_ddg()` in `obscura.py`), and
that endpoint is unreachable/blocked here — confirmed with a direct
`urllib.request.urlopen` probe (2 attempts, both `URLError: urlopen error
timed out`), while a plain `https://example.com` GET succeeds immediately.
This matches the exact failure mode `experiments/salva_v2/harness/README.md`
already flagged: "`SEARXNG_URL`/`ddg_html`/`obscura_browser`, none of which
are reliably reachable without a fully provisioned deployment... `ddgs` is
the provider found reliable in this kind of environment."

**3. Ran `ObscuraBrowserRetriever.search()` directly (not through the full
pipeline, since it never gets past discovery) against 3 representative
domains/queries drawn from `task_set_v2.json` tasks** (`single-01-tsmc`,
`single-02-naturehike`, `single-03-cncf`):

| domain | query | elapsed | results | attempt error |
|---|---|---:|---:|---|
| `tsmc.com` | "investor relations" | 8.0s | 0 | `ddg_no_results` |
| `naturehike.com` | "distributor DACH" | 8.0s | 0 | `ddg_no_results` |
| `cncf.io` | "founding members" | 8.0s | 0 | `ddg_no_results` |

All three time out at exactly the configured `request_timeout` (8s) with
zero results — consistent with the DDG HTML discovery endpoint being
blocked/rate-limited at the network level in this sandbox, not a
task-specific or content-specific failure. `ddgs` (used as the general
search provider throughout the harness) was re-verified as reachable in the
same session (3 results for a TSMC query via `DDGS().text(...)`), confirming
the sandbox's asymmetry: primp/TLS-impersonated requests (`ddgs`) get
through, plain `urllib` POSTs to `html.duckduckgo.com` do not.

## Why no pipeline-level comparison was attempted

`ObscuraBrowserRetriever` is not a general web-search source — per its own
docstring and `registry.py`'s default-chain wiring, it's a **site-scoped
batch content-fetch fallback** (registered for `radar`/`pirate` strategies,
requires `policy.site_domains`, replaces `site_html` when the binary is
present). Its discovery mechanism (`site:{domain} {query}` via DDG HTML) is
a hard dependency, not an optional enhancement — with it blocked, the
provider structurally cannot return anything in this sandbox regardless of
which task, query, or domain is used. Building a fixture-harness-style A/B
(pool-with-obscura vs pool-without) would only ever produce "obscura
contributes 0 candidates on every task," which is already fully demonstrated
by the 3-task probe above without needing the full 18-task harness run.

## What would be needed to actually run this

To get a real answer to "does Obscura's JS-rendering source contribute
candidates ddgs doesn't":

1. **Outbound network access to `html.duckduckgo.com` (or an alternative
   discovery path)** from the execution environment — the current sandbox's
   network egress appears to allow `ddgs`'s TLS-impersonated requests but
   not plain `urllib` POSTs to that specific endpoint. A real deployment (or
   a sandbox with broader/different egress rules) would need to be used
   instead.
2. Once discovery works, the actual test is straightforward with the
   existing harness pattern: record fixtures for a small task subset with
   `ObscuraBrowserRetriever` added to the provider chain
   (`RetrievalProviderConfig(kind="obscura_browser")` + `site_domains` set to
   each task's known target domain(s)), then diff the recorded candidate
   URLs against the existing `ddgs`-only fixtures for the same tasks to see
   whether Obscura's JS-rendered fetch surfaces pages `ddgs`'s search-result
   snippets missed (e.g. JS-gated content, SPA-rendered listings).
3. This is source-comparison, not pipeline-comparison — no changes to
   `core/controller.py`, `processing/confidence.py`, or `enrichment/rerank.py`
   are implied; it would only add a fixture-recording run and a diff script
   under `experiments/salva_v2/`.

## Files touched by this eval

None outside this document. No production code (`retrieval/`,
`core/controller.py`, `processing/confidence.py`, `enrichment/rerank.py`) was
modified. Probes were run ad hoc via `.venv/bin/python3 -c "..."` and are not
persisted as scripts, since the outcome (structural failure at the discovery
step, reproducible in under a minute) doesn't warrant a standing harness
addition until the network precondition in "What would be needed" is met.
