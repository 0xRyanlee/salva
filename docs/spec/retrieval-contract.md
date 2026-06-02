# Retrieval Contract Spec

This spec defines retrieval behavior independent of any specific provider.

## Core behavior

- Retrieval should be chosen after a probe stage classifies the target topology.
- Retrieval is multi-provider.
- Retrieval may fallback across providers when primary quality is low or a provider fails.
- Retrieval may expand in parallel when the first pass quality score is below threshold.
- Retrieval output must be normalized before it reaches the pipeline.

## Request-level controls

The request can influence retrieval via:

- `retrieval.mode`
- `retrieval.providers`
- `retrieval.site_domains`
- `intent.domain_hints`
- `objective`
- `probe.topology` when a higher-level planner is present

## Retrieval modes

- `auto`: local-first with fallback
- `local_first`: prefer self-hosted providers
- `wall_guarded`: block public fallback providers

## Quality gating

The retrieval layer must score the first pass before deciding whether to expand.

Current decision factors:

- coverage
- domain diversity
- snippet richness

If quality falls below threshold, additional healthy providers may run in parallel and the results are merged and deduped.

## Debug checks

- If the wrong route was chosen, inspect the probe classification before changing provider logic.
- If the system returns too little diversity, inspect provider health and the quality threshold.
- If a local provider is down, the runtime should prefer recovery or clear fallback behavior over silent failure.
- If a result set looks biased, check region/language defaults on the provider layer before changing the pipeline.
