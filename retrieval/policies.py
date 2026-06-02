from __future__ import annotations

from salva_core.schemas import RetrievalPolicy


def resolve_retrieval_policy(policy: RetrievalPolicy) -> RetrievalPolicy:
    mode = policy.mode

    if mode == "normal":
        return policy.model_copy(
            update={
                "request_timeout": min(policy.request_timeout, 10.0),
                "request_delay": max(0.2, policy.request_delay),
                "cooldown_seconds": max(45.0, policy.cooldown_seconds),
                "max_instances_per_query": min(policy.max_instances_per_query, 2),
                "html_fallback": False,
            }
        )

    if mode == "cautious":
        return policy.model_copy(
            update={
                "request_timeout": max(policy.request_timeout, 18.0),
                "request_delay": max(1.0, policy.request_delay),
                "cooldown_seconds": max(120.0, policy.cooldown_seconds),
                "max_instances_per_query": min(policy.max_instances_per_query, 3),
                "html_fallback": True,
            }
        )

    if mode == "wall_guarded":
        return policy.model_copy(
            update={
                "request_timeout": max(policy.request_timeout, 20.0),
                "request_delay": max(1.2, policy.request_delay),
                "cooldown_seconds": max(180.0, policy.cooldown_seconds),
                "max_instances_per_query": min(policy.max_instances_per_query, 5),
                "html_fallback": True,
                "engine_rotation": True,
                "region_hint": policy.region_hint or "wall_guarded",
            }
        )

    return policy.model_copy(
        update={
            "request_timeout": max(policy.request_timeout, 15.0),
            "request_delay": max(0.5, policy.request_delay),
            "cooldown_seconds": max(90.0, policy.cooldown_seconds),
            "max_instances_per_query": min(policy.max_instances_per_query, 4),
            "html_fallback": True,
        }
    )
