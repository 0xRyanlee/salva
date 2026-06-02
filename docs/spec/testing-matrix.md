# Testing Matrix Spec

This spec defines the minimum regression scope for common Salva changes.

## Rules

- Prefer pipeline-level regression over full-suite runs during normal development.
- Run the smallest test set that covers the changed contract surface.
- Run the full suite only after contract changes, large refactors, or before release.

## Change Surface → Test Scope

| Change surface | Minimum tests |
|----------------|---------------|
| `core/query_strategy.py`, `core/domain_vocab.py`, `core/controller.py` | `tests/test_query_strategy.py`, `tests/test_query_profiles.py`, `tests/test_domain_vocab.py`, `tests/test_routes.py` |
| `retrieval/registry.py`, `retrieval/router.py`, `retrieval/sources/*` | `tests/test_provider_registry.py`, `tests/test_provider_registry_unit.py`, `tests/test_routed_retriever_merge.py`, source-specific retriever tests |
| `processing/*` | `tests/test_processing_pipeline.py`, `tests/test_transforms.py`, scorer / dedup / extractor tests |
| `salva_core/persistence/*`, `salva_core/worker.py`, `salva_core/jobs.py` | `tests/test_jobs.py`, persistence query tests, run/result persistence tests |
| `salva_core/pricing.py`, `salva_core/navigation.py`, `salva_core/semantic.py` | module-specific tests plus downstream API tests if responses change |
| `apps/api/*` | endpoint tests that touch the changed route(s) |
| `apps/mcp/*` | MCP auth/server tests |
| `salva_sdk/*` | SDK tests only |
| `enrichment/*` | plugin tests and any caller surface that consumes enrichment output |

## Escalation Levels

### Level 1: Local Unit / Pipeline Regression

Use when changing one module or one contract family.

Examples:

- adjust a provider parser
- add a new route field
- fix one scorer branch

### Level 2: Integration Regression

Use when changing shared contracts or cross-layer behavior.

Examples:

- objective mapping changes
- provider fallback logic
- persistence schema changes
- API response shape changes

### Level 3: Full Regression

Use when:

- updating canonical specs
- refactoring shared types
- changing persistence or routing behavior in a way that may affect many callers
- preparing a release

## Debug Priority

If a bug can be reproduced with one route or one provider family, fix and test that slice first.
Do not start with the full suite unless the issue is clearly cross-cutting.
