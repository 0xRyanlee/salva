"""Merge duplicate CanonicalEntity records within a single discovery run
using nomenklatura's scoring + judgement model (step 3-4 of
experiments/salva_v2/ENTITY_RESOLUTION_INTEGRATION_EVAL.md).

Step 3 finding: core/controller.py has no entity-level merge call site at
all today -- salva_core/service.py builds one CanonicalEntity per surviving
search result with no subsequent dedup. This module is new capability, not
a replacement of live logic. It is NOT wired into service.py yet (see board
salva-entity-resolution-nomenklatura-integration) -- deliberately, since
wiring changes user-visible output and deserves an opt-in flag decision of
its own, matching how enable_query_proposal shipped off-by-default first.

Only compares entities of the same FtM schema (via ftm_adapter's mapping) --
comparing e.g. a Person against a Company is never a legitimate duplicate
pair and wastes a nomenklatura.matching call.
"""
from __future__ import annotations

from itertools import combinations

from nomenklatura.db import get_engine, get_metadata, make_session
from nomenklatura.judgement import Judgement
from nomenklatura.matching import DefaultAlgorithm
from nomenklatura.resolver import Resolver

from salva_core.resolvers.ftm_adapter import canonical_entity_to_proxy
from salva_core.schemas import CanonicalEntity

DEFAULT_MERGE_THRESHOLD = 0.7


def make_ephemeral_resolver(db_url: str = "sqlite:///:memory:") -> Resolver:
    """A resolver backed by a fresh in-memory judgement store, scoped to one
    call site. Whether judgements should persist ACROSS runs (a durable
    nomenklatura DB shared machine-wide, vs a fresh one per run) is a
    separate wiring decision not made yet -- this is the safe default that
    doesn't accidentally start accumulating a permanent cross-run store
    before that decision is made."""
    engine = get_engine(db_url)
    get_metadata().create_all(bind=engine)
    return Resolver(make_session(db_url), create=True)


def resolve_duplicate_entities(
    entities: list[CanonicalEntity],
    resolver: Resolver | None = None,
    threshold: float = DEFAULT_MERGE_THRESHOLD,
) -> list[CanonicalEntity]:
    """Returns a new list with score>=threshold pairs merged into one
    CanonicalEntity (the earlier one in input order survives; source_urls/
    tags/evidence from the merged-away entity are folded in, nothing is
    silently dropped). O(n^2) within each schema group -- fine at
    single-run entity counts (tens, not thousands); revisit with
    nomenklatura's Index/blocking if that stops being true."""
    if len(entities) < 2:
        return list(entities)

    active_resolver = resolver if resolver is not None else make_ephemeral_resolver()
    proxies = {entity.entity_id: canonical_entity_to_proxy(entity) for entity in entities}
    config = DefaultAlgorithm.default_config()

    parent: dict[str, str] = {entity.entity_id: entity.entity_id for entity in entities}

    def find(entity_id: str) -> str:
        while parent[entity_id] != entity_id:
            parent[entity_id] = parent[parent[entity_id]]
            entity_id = parent[entity_id]
        return entity_id

    def union(a: str, b: str) -> None:
        root_a, root_b = find(a), find(b)
        if root_a != root_b:
            parent[root_b] = root_a

    by_schema: dict[str, list[CanonicalEntity]] = {}
    for entity in entities:
        by_schema.setdefault(entity.entity_type, []).append(entity)

    for group in by_schema.values():
        for left, right in combinations(group, 2):
            left_proxy, right_proxy = proxies[left.entity_id], proxies[right.entity_id]
            result = DefaultAlgorithm.compare(left_proxy, right_proxy, config)
            if result.score >= threshold:
                active_resolver.decide(
                    left.entity_id, right.entity_id, Judgement.POSITIVE, score=result.score
                )
                union(left.entity_id, right.entity_id)

    groups: dict[str, list[CanonicalEntity]] = {}
    for entity in entities:
        groups.setdefault(find(entity.entity_id), []).append(entity)

    return [_merge_group(group) for group in groups.values()]


def _merge_group(group: list[CanonicalEntity]) -> CanonicalEntity:
    if len(group) == 1:
        return group[0]
    survivor = group[0].model_copy(deep=True)
    seen_urls = set(survivor.source_urls)
    seen_tags = set(survivor.tags)
    for duplicate in group[1:]:
        for url in duplicate.source_urls:
            if url not in seen_urls:
                survivor.source_urls.append(url)
                seen_urls.add(url)
        for tag in duplicate.tags:
            if tag not in seen_tags:
                survivor.tags.append(tag)
                seen_tags.add(tag)
        survivor.evidence.extend(duplicate.evidence)
        for key, value in duplicate.attributes.items():
            survivor.attributes.setdefault(key, value)
        survivor.confidence = max(survivor.confidence, duplicate.confidence)
        survivor.score = max(survivor.score, duplicate.score)
    return survivor
