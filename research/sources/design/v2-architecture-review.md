
# SALVA_V2_ARCHITECTURE_REVIEW.md
Salva v2 — Query Intelligence & Lead Quality Runtime
Author: Ryan + Architecture Review
Audience: Antigravity / Karl
Status: Architecture Direction

---

# 1. Purpose

Salva should evolve from a multi‑mode search skill into a Leads Intelligence Runtime.

The current implementation mixes:

- conceptual search strategies
- experimental features
- early pipeline scripts

This document defines the target architecture, gaps in the current system, and implementation priorities for Salva v2.

Focus:

- higher lead quality
- observable search behavior
- iterative query intelligence
- stable data structures

---

# 2. Current System Diagnosis

Current Salva pipeline:

seed queries
→ search
→ qualification
→ export

This is a single‑pass pipeline.

But the intended design includes:

- iterative query expansion
- keyword graph
- relevance feedback
- semantic memory
- OSINT discovery
- lead enrichment

There are three major gaps.

---

## Static Query System

Queries are currently strings rather than structured objects.

Example today:

toy distributor japan

Target structure:

{
  "market": "Japan",
  "industry": "toy",
  "product": "plush",
  "role": "distributor",
  "objective": "b2b_leads"
}

---

## Missing Search Telemetry

System does not store:

- query success rate
- qualification score distribution
- rejection reasons
- noise frequency
- duplicate rate

Without telemetry the system cannot learn.

---

## Keyword Graph Not Implemented

Documents describe:

Keyword Graph
Dynamic Weights
Anchor Mode
Radar Mode

But runtime lacks:

- node schema
- weight updates
- feedback signals
- exploration strategy

---

# 3. Target Architecture

Salva v2 should contain five layers.

Layer 1 — Intent Layer
Layer 2 — Query Intelligence
Layer 3 — Retrieval
Layer 4 — Lead Processing
Layer 5 — Persistence

---

# Layer 1 — Intent Layer

Convert user goals into structured intent.

Example:

{
  "market": "Japan",
  "industry": "toy",
  "product": "plush",
  "role": "distributor"
}

Responsibilities:

- normalize search objective
- define search scope
- set constraints

---

# Layer 2 — Query Intelligence

Modules:

- Keyword Graph
- Expansion Engine
- Negative Term Engine
- Query Family Generator
- Multi‑Round Controller
- Search Telemetry

---

## Keyword Graph

Node example:

{
  "phrase": "vinyl toy distributor",
  "market": "US",
  "role": "distributor",
  "category": "designer toy",
  "weight": 0
}

Edges represent:

- synonym
- specialization
- region
- product variant

---

## Expansion Engine

Sources:

- vocabulary lists
- synonym dictionary
- region variants
- LLM suggestions

Example:

toy → plush → stuffed toy → collectible toy

distributor → wholesaler → importer → supplier

---

## Negative Term Engine

Examples:

blog
museum
review
job
news
report

Types:

global negatives
market negatives
experimental negatives

---

## Query Family Generator

Example family:

"plush distributor" Japan
"toy wholesaler" Tokyo
"collectible toy retailer" Osaka

---

## Multi‑Round Controller

Round 1: seed queries

Round 2: expansion

Round 3: noise filtering

Each round uses telemetry feedback.

---

## Search Telemetry

Example record:

{
  "query": "plush distributor Japan",
  "round": 2,
  "results": 25,
  "qualified": 4,
  "avg_score": 1.7,
  "reject_reasons": ["blog","consumer_only"]
}

---

# Layer 3 — Retrieval

Retrieval strategies:

Dive — operator search

Anchor — keyword graph expansion

Radar — semantic discovery

Pirate — deep OSINT crawl

These are strategies, not the core architecture.

---

# Layer 4 — Lead Processing

Pipeline:

extraction
→ normalization
→ deduplication
→ qualification
→ enrichment
→ validation
→ confidence scoring

---

## Lead Schema

company_name
domain
market
industry
role
qualification_id
contact_status
confidence
source_url

---

# Layer 5 — Persistence

Two storage types:

Structured Lead Store

Vector Database

Structured DB holds canonical lead data.

Vector DB stores semantic context.

---

# 4. Implementation Phases

Phase A — Data Foundations

- qualification_id
- deduplication
- lead schema
- reject taxonomy
- telemetry storage

Phase B — Query Intelligence MVP

- query family schema
- expansion vocabulary
- negative term list
- multi‑round controller

Phase C — Feedback Integration

- qualification feedback
- noise pattern detection
- query success statistics

Phase D — Lead Quality

- email discovery
- validation
- confidence scoring
- review gate
- cold email drafts

Phase E — Graph Optimization

- dynamic keyword weights
- anchor expansion
- exploration strategy

---

# 5. Non‑Goals (for now)

Do not implement yet:

- automated email sending
- full autonomous graph control
- uncontrolled OSINT crawling

---

# 6. Success Criteria

System succeeds when:

- queries improve based on data
- noise is automatically filtered
- duplicate leads decrease
- qualification feedback improves search
- leads become reliable B2B prospects

---

# 7. Summary

Salva v2 transforms the system from:

static search pipeline

into:

Query Intelligence + Lead Quality Runtime
