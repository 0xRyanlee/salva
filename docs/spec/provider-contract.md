# Provider Contract Spec

This spec defines the supported provider types and their contract shape.

## Supported provider kinds

- `searxng`
- `whoogle`
- `ddgs`
- `exa`
- `hackernews_algolia`
- `openalex`
- `arxiv`

## Common fields

Providers may define:

- `name`
- `type`
- `base_url`
- `timeout_sec`
- `priority`
- `jitter_sec`
- `region`
- `objectives`

## Contract rules

- Local self-hosted providers should default to zero jitter.
- Public providers may use modest jitter and fallback behavior.
- API-key providers must be skipped cleanly when the required secret is missing.
- Objective-gated providers must only activate when the route objective matches.

## Provider-specific notes

- `searxng` and `whoogle` are general web retrieval adapters.
- `ddgs` is a fallback provider and should not be the only source of truth for broad discovery.
- `exa` is semantic and requires `EXA_API_KEY`.
- `hackernews_algolia`, `openalex`, and `arxiv` are supplemental signal sources, not replacements for web retrieval.

## Debug checks

- If a provider never runs, check policy caps and objective gating.
- If a provider returns biased results, inspect locale defaults and query language assumptions.
- If a local SearXNG instance is present but unreachable, the debug path should verify container state and port mapping before asking the caller to reinstall anything.
