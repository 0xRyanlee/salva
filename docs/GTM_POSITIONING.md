# GTM Positioning Research — draft, not for external use

> ⚠️ **待 owner 核可才能對外發佈。** Everything below is a positioning
> *draft* grounded in this session's real experimental data, not a decided
> strategy. No claim here should be copied into a landing page, pitch deck,
> or public README section without the owner explicitly signing off first.
> This document itself makes zero claims beyond what the cited data
> supports — that discipline should carry through to whatever gets
> published, not get diluted along the way.

**Date:** 2026-07-03. Grounded in `experiments/salva_v2/ANALYSIS_FINDINGS.md`,
`RESCORE_COMPARISON.md`, `STRUCTURAL_VALUE_FINDINGS.md`,
`NOISE_FILTER_AUDIT.md`, and `docs/DISTRIBUTION_STRATEGY.md` — not the
pre-Phase-3 README self-description, which this session's own data has
already shown to overstate Salva's effectiveness (see
`docs/product-brief.md`'s "⚠️ 待 owner 拍板" section for that unresolved
tension, still open).

## 1. What Salva actually, verifiably helps with (the factual basis)

Per `ANALYSIS_FINDINGS.md` and confirmed unchanged after a scorer fix
attempt in `RESCORE_COMPARISON.md` (17/18 tasks showed no change from the
fix — this pattern is stable, not a temporary bug):

- **Cross-language (Chinese↔English) entity/company resolution is Salva's
  one consistently-demonstrated strength.** 5 of 6 `crosslang` tier tasks
  in `task_set_v1.json` had Salva's own scoring layer contribute genuine
  qualified entities (vs. 1 of 6 for English-only single-entity lookups,
  and 0 of 6 for `find_partnership_signals`/relationship-discovery
  queries). Examples with cited source: 台積電→TSMC, 華碩→ASUS, 宏碁→Acer,
  鴻海→Foxconn, 中華電信→Chunghwa Telecom all resolved correctly with
  qualified confidence (`ANALYSIS_FINDINGS.md` table).
- **Efficiency, not accuracy, is the other defensible claim.** Arm B
  (+Salva) used 14% fewer total requests than Arm A (bare search) for
  equivalent-or-better recall across all 18 tasks (`ANALYSIS_FINDINGS.md`).
  On raw answer-finding accuracy, the honest result is **17 ties, 1 Arm B
  win, 0 Arm A wins** — not "Salva finds better answers," but "Salva
  reaches the same answer with less search budget," specifically in the
  domains where its scoring layer actually contributes (see above).
- **What does NOT currently support a positioning claim**: relationship/
  partnership discovery (`find_partnership_signals` — 0/6 contribution
  both before and after the scorer fix, root-caused to a signal-vocabulary/
  trusted-source mismatch in `RESCORE_COMPARISON.md`, not yet fixed);
  `pilot`'s next-step suggestions (`STRUCTURAL_VALUE_FINDINGS.md` found no
  improvement from tested suggestions, one produced a false positive);
  route/topology selection as a quality differentiator (sensible query
  classification, but doesn't predict outcome quality per the same
  document). `audit`'s quality scoring is a positive, real finding but is
  an internal/operational feature, not something an end user would choose
  Salva *for*.

## 2. Target audience fit, mapped against what's actually proven

| Audience | Fit with proven strength | Fit with proven weakness | Verdict |
|---|---|---|---|
| **OSINT / investigative researchers** | High — cross-script entity resolution (台積電↔TSMC-class problems) is core, recurring OSINT work: resolving a subject/company name across Chinese/English sources, sanctions lists, corporate registries. Directly matches the one proven strength. | Multi-hop relationship discovery ("who is connected to whom") is exactly what OSINT work often also needs, and is exactly the currently-broken capability. | **Best current fit, with an explicit caveat to disclose**: strong for entity resolution, not yet for relationship mapping. |
| **Business dev / partnership discovery teams** | Low — this audience's core need ("who partners with X", "who are X's competitors/customers") maps almost exactly onto `find_partnership_signals`/`find_market_activity`, Salva's *worst*-performing objective (0/6 contribution). | -- | **Do not position to this audience yet.** This would be the single easiest way to overclaim — the objective these users care about most is the one with zero verified evidence behind it. Revisit after a scorer recalibration (flagged as a follow-up in `RESCORE_COMPARISON.md`, not yet done) and a re-test. |
| **Developers building agents on Claude Code (MCP tool consumers)** | Medium-high — this is the exact usage pattern Phase 3 was designed around ("Claude Code invoking Haiku, using Salva as an MCP tool"), and the efficiency finding (14% fewer requests) is a real, generic value prop for this audience regardless of query type. `docs/DISTRIBUTION_STRATEGY.md` confirms all four researched distribution channels (PyPI, GHCR, MCP directories, Desktop extension) target exactly this audience. | This audience will reasonably expect broad, general-purpose capability from "just another MCP search tool" — Salva's proven value is narrow (cross-language entity resolution + modest efficiency), not general research superiority. Overselling generality to this technically-literate audience is a fast way to get publicly fact-checked. | **Good fit for the distribution channels already researched, with a scoped, honest capability claim** — not "a better research agent," but "an efficient, MCP-native tool for cross-language entity resolution, with lower request overhead than bare search." |

## 3. Competitive positioning — n-ary hyperedge/HIF as differentiation, honestly scoped

`docs/product-brief.md`'s existing comparison table (Perplexity/Tavily/Exa/
Google PSE) is aspirational, not yet verified against actual competitor
products (Phase 3 only compared vs. bare Haiku, never against a real
competing service — `product-brief.md`'s own "⚠️ 待 owner 拍板" section
already flags this). This document does not resolve that gap; it only adds
what Phase 3's data can honestly say about the one differentiator that
*is* implemented and real: the n-ary hypergraph/HIF representation.

**Honest framing, not "Salva's graph beats Tavily's flat results" (unverified):**
"Salva stores results as a queryable hypergraph (entities/relations/
evidence/sources), not just a ranked list — this is a real, shipped,
tested feature (`salva_core/schemas.py`, HIF export via `salva_graph_export`),
independent of the retrieval-accuracy question Phase 3 tested." What Phase
3 and `STRUCTURAL_VALUE_FINDINGS.md` do NOT establish is whether that
structure produces better *research outcomes* than a flat result list would
— that's a genuinely separate, untested claim (same gap `product-brief.md`
already flags for route/pilot/audit). **Do not claim the hypergraph itself
improves research quality until that's tested** — claim only that it
exists and is queryable, which is verifiably true.

## 4. Distribution channels this positioning should assume

Per `docs/DISTRIBUTION_STRATEGY.md` (all free, all research-only, nothing
published yet):
- **PyPI** — highest readiness, wheel builds clean today.
- **MCP directories** (Official MCP Registry, Smithery, PulseMCP, Glama.ai/mcp) — the natural discovery channel for the "developers building agents on Claude Code" audience identified above; sequenced after PyPI/GHCR since these mostly point at where the package lives.
- **GHCR (Docker)** — needs the dev-extras image-weight issue addressed first (flagged, not fixed, in `DISTRIBUTION_STRATEGY.md`).
- **Claude Desktop `.mcpb`** — deferred, targets a lower-priority audience per that document's own analysis.

Any positioning copy drafted from this document should assume discovery
happens through an MCP directory listing or a `pip install`, not a
marketing landing page — matching the audience analysis in section 2.

## 5. Draft positioning statements (drafts only — cite the data, don't round up)

Presented as candidate one-liners with their evidentiary basis, for the
owner to pick from, edit, reject, or request more validation before using
any of them:

1. *"Salva resolves company and entity names across Chinese and English
   sources — the same query that returns zero relevant results from a
   bare agent search."* — Supported by: `ANALYSIS_FINDINGS.md`'s
   `crosslang` tier data (5/6 tasks). **Caveat to keep attached**: this is
   about resolving *which entity a name refers to*, not general research
   depth.
2. *"An MCP-native tool that answers the same questions with 14% fewer
   search requests."* — Supported by: `ANALYSIS_FINDINGS.md`'s
   efficiency finding (38 vs 44 total requests, Arm B vs Arm A). **Caveat**:
   this is an average across all 18 tasks including ones where Salva
   contributed nothing; framing it as a universal guarantee would overclaim.
3. *"Structured, queryable research output — entities, relations, and
   evidence as a walkable hypergraph, not just a list of links."* —
   Supported by: the feature genuinely exists and is tested
   (`salva_core/schemas.py`, `salva_graph_export`). **Caveat**: no evidence
   yet that this structure improves research *outcomes* — frame as a
   capability, not a proven quality advantage.

**Explicitly NOT supported by current data, do not draft copy claiming
these**: "better than direct search" (contradicted by the 17-tie result),
"finds partnerships/relationships" (0/6, the worst-performing capability),
"smarter next-step suggestions via pilot" (tested negative), "route
selection improves results" (tested, no correlation found).

## Guardrails honored

No landing-page/marketing copy was written — only positioning research
and cited draft statements, per this card's scope. No pricing/business
model decision was made — that's explicitly owner-lane. Every claim above
traces to a specific file this session produced; nothing is asserted from
impression or the pre-Phase-3 README's self-description.
