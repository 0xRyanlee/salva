# Rescore Comparison — Did the scorer fix convert ties into wins?

**Date:** 2026-07-03
**Answer, upfront: no.** After `salva-p35-scorer-partnerships-domain` (added the missing
`"partnerships"` `DOMAIN_CONFIGS` entry) and `salva-p35-scorer-threshold-wiring`
(wired domain-calibrated thresholds into the production path), all 18 tasks in
`task_set_v1.json` were re-run for **Arm B only** (Arm A is bare search and
doesn't touch the scorer — original results reused unchanged from
`experiments/salva_v2/raw_results/*_A.json`). **17 of 18 tasks show the exact
same `qualified_count` as the original Phase 3 run.** The one task that
changed (`multihop-03-naturehike-dach`, 0 → 1) changed to a **wrong match**,
not a real improvement — see below.

This is a genuine, valuable null result, not a failed card. It proves the
fix was **necessary but not sufficient**: it correctly stopped
`find_partnership_signals` queries from silently falling back to an empty
`ScorerConfig()`, but exposed two *different*, deeper problems that a
threshold/domain-config fix alone can't solve.

## Full comparison table

| task_id | pre-fix qualified_count | post-fix qualified_count | changed? |
|---|---:|---:|---|
| single-01-tsmc | 3 | 3 | no |
| single-02-naturehike | 0 | 0 | no |
| single-03-cncf | 0 | 0 | no |
| single-04-mediatek | 0 | 0 | no |
| single-05-advantech | 0 | 0 | no |
| single-06-gleif | 0 | 0 | no |
| crosslang-01-tsmc | 5 | 5 | no |
| crosslang-02-asus | 4 | 4 | no |
| crosslang-03-acer | 4 | 4 | no |
| crosslang-04-foxconn | 4 | 4 | no |
| crosslang-05-chunghwa-telecom | 7 | 7 | no |
| crosslang-06-delta | 0 (noise) | 0 | no |
| multihop-01-cncf-founders | 0 | 0 | no |
| multihop-02-tsmc-customers | 0 | 0 | no |
| multihop-03-naturehike-dach | 0 | **1** | **yes -- but wrong match, see below** |
| multihop-04-mediatek-brands | 0 | 0 | no |
| multihop-05-gleif-regulators | 2 (low-conf) | 2 (low-conf) | no |
| multihop-06-advantech-cloud | 0 | 0 | no |

Raw per-task rerun output: `experiments/salva_v2/raw_results_rerun/*_B.json`.

**multihop-03's "change" is not a real improvement.** The single qualified
entity post-fix was an unrelated Medisca DACH sales-job posting (confidence
0.38) -- not a Naturehike signal of any kind. If anything this is evidence
the qualification gate is *not selective enough* on this domain now, not
evidence it got smarter.

## Single/cross-language tier (companies domain): unchanged as expected

None of these 12 tasks use `domain="partnerships"` -- they map to
`domain="companies"`, which already had a real `DOMAIN_CONFIGS` entry
*before* this fix (confirmed by the Explore agent research that scoped
`salva-p35-scorer-partnerships-domain`). Neither fix touched the
`"companies"` config. Zero change here is exactly what should happen --
this is not evidence the fix failed, it's confirmation the fix stayed
inside its stated scope.

## Multi-hop tier (partnerships domain): fixed the wrong-fallback bug, but a deeper vocabulary/trust-list mismatch remains

Inspecting `reject_reasons` from a live rerun of `multihop-01-cncf-founders`
(via `telemetry.reject_reasons`, not guessed) shows the fix did what it was
supposed to do -- results are now genuinely scored against real
`"partnerships"` signal terms instead of an empty fallback config -- but
still lose on `"low_signal"`. Two separate, previously-invisible problems
surfaced once the fallback bug stopped masking them:

1. **`high_signals`/`med_signals` vocabulary mismatch.** The signal terms
   added in `salva-p35-scorer-partnerships-domain` ("strategic alliance",
   "memorandum of understanding", "MOU", "joint venture", "signed
   agreement") describe *formal partnership-deal announcements*. Real
   content answering "which companies were CNCF founding members" or "which
   brands use MediaTek Dimensity" doesn't use that vocabulary at all -- it
   just states facts ("Google, Cisco, IBM... were founding members",
   "Xiaomi's flagship phones ship with Dimensity 9000"). `find_partnership_
   signals` as an objective covers a *broader* concept (any documented
   relationship/membership/adoption) than the signal list was designed for
   (formal deal-signing language).
2. **`trusted_sources` gap.** `multihop-04-mediatek-brands`'s rerun surfaced
   this directly: Salva's own `noise_domains`/`untrusted_source` telemetry
   flagged `en.wikipedia.org`, `www.mediatek.com`, `www.intel.com`,
   `www.amd.com`, `www.hp.com` as *untrusted* -- official company domains
   and Wikipedia are exactly the authoritative sources for "who partners
   with X" questions, but the `"partnerships"` `trusted_sources` list
   (inherited from `core/domain_vocab.py`'s business-press-focused
   `source_hints`: linkedin.com, businesswire.com, prnewswire.com,
   crunchbase.com, techcrunch.com, venturebeat.com) has no entry for either.
   That list fits "read about a deal in the trade press" content, not
   "read a company's own product page describing its own partner
   ecosystem."

Both of these are real, but they are **new findings from this rerun**, not
something this card is scoped to fix (per its own guardrail: "這張卡不做任何
程式修改，只跑實驗、寫對照分析"). They're flagged here for a future card, not
patched in this one.

## Retrieval-quality confound worth disclosing

Before running the full rerun, a manual sanity check on
`multihop-01-cncf-founders` surfaced something separate from the scorer
question entirely: one live retrieval attempt for "CNCF founding members"
returned completely unrelated Indonesian-language "what is an algorithm"
tutorial content (verified reproducible, 3/3 identical retries at the time).
A parallel check confirmed this was query-specific, not systemic -- the same
retriever returned clean, relevant TSMC results for a different query in the
same session. By the time the full agent-driven rerun ran (a few minutes
later, via a fresh Haiku agent invocation), `multihop-01`'s rerun no longer
showed that specific garbage pattern in its raw candidates (per the agent's
own report, the CNCF founding-member announcement text did surface, it just
still didn't clear `low_signal`) -- consistent with `EXPERIMENT_PROTOCOL.md`'s
own disclosed limitation that live network/provider conditions drift
between runs. This is disclosed for completeness, not offered as an excuse
for the null result above -- the reject_reasons diagnosis (vocabulary +
trust-list gaps) stands on its own regardless of this transient retrieval
noise.

## Answering the card's own two questions directly

**"原本 0/6 貢獻的 multihop 題目，修完之後有幾題轉正？"** Zero. All 6 stayed
at their pre-fix qualified_count (0, 0, 0→1-wrong-match, 0, 2, 0).

**"原本 17 平手裡，有幾題從平手變成 Arm B 真贏？"** Zero. No task's Arm B
outcome materially improved; `multihop-03`'s nominal qualified_count uptick
is a false positive (wrong entity), not a real win, and doesn't change the
tier's business-outcome verdict from `ANALYSIS_FINDINGS.md`.

## What this means going forward

The scorer fix was still worth landing -- it removed a real, silent
fallback-to-empty-config bug and made `domain_threshold()` actually reach
production, which is correct regardless of whether it moved this particular
18-task set's numbers. But it confirms the diagnosis needs one more layer:
**the `"partnerships"` domain's signal vocabulary and trusted-source list
are calibrated for press-release-style deal announcements, not for the
broader "who has a documented relationship with X" queries
`find_partnership_signals` is actually asked to answer.** A follow-up card
recalibrating `DOMAIN_CONFIGS["partnerships"]`'s `high_signals`/
`med_signals`/`trusted_sources` against the *actual* vocabulary seen in this
rerun's raw candidates (not domain_vocab.py's pre-existing, deal-announcement-
flavored list) is the next concrete, evidence-backed step -- not carded here,
left for the owner/next planning pass to prioritize against the rest of the
P3.5 backlog.
