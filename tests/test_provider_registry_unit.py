from __future__ import annotations

from retrieval import registry
from salva_core.schemas import RetrievalPolicy, RetrievalProviderConfig


def test_apply_provider_overrides_merges_and_normalizes_lists() -> None:
    policy = RetrievalPolicy(
        site_domains=["WWW.Example.com", "alpha.example"],
        extra_instances=["A", "b"],
    )
    config = RetrievalProviderConfig(
        kind="whoogle",
        request_timeout=7.5,
        request_delay=0.25,
        cooldown_seconds=33.0,
        max_instances_per_query=2,
        allow_public_fallback=False,
        prefer_builtin_instances=False,
        html_fallback=False,
        engine_rotation=False,
        site_domains=["example.com", "beta.example"],
        extra_instances=["b", "C"],
    )

    update = registry._apply_provider_overrides(policy, config)

    assert update == {
        "request_timeout": 7.5,
        "request_delay": 0.25,
        "cooldown_seconds": 33.0,
        "max_instances_per_query": 2,
        "allow_public_fallback": False,
        "prefer_builtin_instances": False,
        "html_fallback": False,
        "engine_rotation": False,
        "site_domains": ["example.com", "alpha.example", "beta.example"],
        "extra_instances": ["a", "b", "c"],
    }


def test_build_provider_chain_falls_back_to_defaults_when_all_configs_disabled() -> None:
    policy = RetrievalPolicy(
        providers=[
            RetrievalProviderConfig(kind="whoogle", enabled=False),
        ]
    )

    providers = registry.build_provider_chain(policy, strategy="dive")

    assert len(providers) == 4
    assert [getattr(provider, "strategy", None) for provider in providers] == ["dive", "dive", "dive", "dive"]


def test_merge_unique_deduplicates_and_strips_www() -> None:
    assert registry._merge_unique(
        ["WWW.Example.com", "alpha.example", ""],
        ["example.com", "beta.example", "ALPHA.EXAMPLE"],
    ) == ["example.com", "alpha.example", "beta.example"]
