from retrieval.policies import resolve_retrieval_policy
from salva_core.schemas import RetrievalPolicy


def test_wall_guarded_policy_strengthens_fallbacks() -> None:
    policy = resolve_retrieval_policy(RetrievalPolicy(mode="wall_guarded"))
    assert policy.html_fallback is True
    assert policy.engine_rotation is True
    assert policy.max_instances_per_query >= 4
    assert policy.region_hint == "wall_guarded"


def test_normal_policy_stays_lightweight() -> None:
    policy = resolve_retrieval_policy(RetrievalPolicy(mode="normal"))
    assert policy.html_fallback is False
    assert policy.max_instances_per_query <= 2
