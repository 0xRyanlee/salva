"""Regression coverage for the ScorerConfig.w_stability plumbing addition.

Pure plumbing card -- no stability computation logic lives here yet (that's
salva_core/stability.py, a separate card). This only proves the new field
exists with a zero default and that _apply_context()'s weight
renormalization is byte-for-byte unaffected by its presence.
"""
from __future__ import annotations

from processing.scorer import QualificationScorer, ScorerConfig
from salva_core.schemas import StabilityPolicy


def test_scorer_config_defaults_w_stability_to_zero() -> None:
    cfg = ScorerConfig()
    assert cfg.w_stability == 0.0


def test_stability_policy_defaults_to_disabled() -> None:
    policy = StabilityPolicy()
    assert policy.enabled is False
    assert policy.min_history == 3
    assert policy.penalty_strength == 0.15


def test_apply_context_normalization_unaffected_by_zero_w_stability() -> None:
    """With w_stability=0, adding it into the total/renormalization sum is a
    no-op -- the other five weights must renormalize to exactly the same
    values as before this field existed."""
    cfg = ScorerConfig()
    adjusted = QualificationScorer._apply_context(cfg, {"notes": ["precision_first"]})

    assert adjusted.w_stability == 0.0
    total = (
        adjusted.w_content + adjusted.w_contact + adjusted.w_signal
        + adjusted.w_region + adjusted.w_source + adjusted.w_recency
        + adjusted.w_stability
    )
    assert abs(total - 1.0) < 1e-9
    # precision_first preset values (processing/scorer.py) renormalized over
    # a total of 1.0 (0.30+0.20+0.22+0.16+0.07+0.05) -- unchanged by adding a
    # zero-valued w_stability term into the same sum.
    assert abs(adjusted.w_content - 0.30) < 1e-9
    assert abs(adjusted.w_source - 0.07) < 1e-9


def test_apply_context_carries_nonzero_w_stability_through_and_renormalizes() -> None:
    """Sanity check for the *next* card (wiring): once a caller sets
    w_stability > 0, _apply_context must actually carry it through the copy
    constructor and include it in renormalization -- not silently drop it."""
    cfg = ScorerConfig(w_stability=0.5)
    adjusted = QualificationScorer._apply_context(cfg, {"notes": []})

    assert adjusted.w_stability > 0.0
    total = (
        adjusted.w_content + adjusted.w_contact + adjusted.w_signal
        + adjusted.w_region + adjusted.w_source + adjusted.w_recency
        + adjusted.w_stability
    )
    assert abs(total - 1.0) < 1e-9
