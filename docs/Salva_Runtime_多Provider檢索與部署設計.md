# Salva Runtime 多 Provider 檢索與部署設計

> Design note only. Canonical provider contract lives in `docs/spec/provider-contract.md`.

## What this note covers

- Provider layering
- Local-first vs public fallback behavior
- Docker / Compose placement
- Where to add new retrieval sources

## Current provider order

1. Local SearXNG
2. Whoogle
3. DDGS
4. Exa
5. Objective-gated sources like HackerNews, OpenAlex, arXiv

## Architecture rule

- `dive / anchor / radar / pirate` are strategy layers
- Providers are execution layers beneath the strategy
- The route catalog decides the path; the provider router executes it

## Deployment rule

- Docker is a packaging choice, not the core architecture
- Self-hosted providers should be preferred when available
- Missing API-key providers should be skipped cleanly, not treated as fatal

## Where to look next

- [spec/provider-contract.md](spec/provider-contract.md)
- [spec/retrieval-contract.md](spec/retrieval-contract.md)
- [spec/debug-playbook.md](spec/debug-playbook.md)
