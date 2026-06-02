# Refactor Slice 01

## Objective

Stabilize contracts before rewriting behavior.

This slice does not try to finish the whole runtime. It creates the single contract layer that all later modules will obey.

## Why This Slice First

Current code has two live schema systems:

- legacy dataclasses in `schema/`
- new API-facing models in `salva_core/schemas.py`

If retrieval, scoring, enrichment, and adapters continue to grow on both sides, the project will fork itself.

## Deliverables

1. One canonical contract package

Create one package that owns:

- discovery request
- discovery response
- canonical entity
- canonical relation
- telemetry
- feedback
- transform options

2. Entity split

Separate:

- shared fields common to all entities
- lead-specific fields
- company-specific fields
- event-specific fields
- activity-signal-specific fields

3. Relation contract

Add typed relations such as:

- `company -> person`
- `company -> event`
- `company -> source`
- `event -> organizer`
- `entity -> evidence`
- `entity -> market`

4. Legacy adapter boundary

Existing modules in `core/`, `processing/`, `retrieval/`, and `enrichment/` may keep their internal shapes temporarily, but their outputs must map through the canonical contract layer before reaching the API.

## Non-Goals

- no provider expansion
- no persistence migration yet
- no cloud auth yet
- no browser automation yet
- no graph backend yet

## Proposed Migration Path

### Step 1

Keep `apps/api/main.py` stable.

### Step 2

Move API-facing request and response shapes into one canonical contracts module.

### Step 3

Create translation helpers:

- `legacy Intent -> canonical discovery intent`
- `legacy UnifiedResult -> canonical entity`
- `legacy telemetry -> canonical telemetry`

### Step 4

Mark legacy `schema/` models as transitional and stop adding new logic to them.

### Step 5

Update controller and processor interfaces to emit canonical outputs.

## Exit Criteria

This slice is complete when:

- there is one obvious source of truth for contracts
- API responses use canonical entities
- legacy modules can still run through adapters
- no new module needs to import both `schema/` and `salva_core/schemas.py`
