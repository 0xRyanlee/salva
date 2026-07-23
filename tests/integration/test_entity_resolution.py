"""step 4 of experiments/salva_v2/ENTITY_RESOLUTION_INTEGRATION_EVAL.md:
resolve_duplicate_entities() merges same-schema near-duplicate
CanonicalEntity records via nomenklatura scoring + judgements. Uses a real
nomenklatura.Resolver (in-memory SQLite session) -- not mocked -- since the
Session/engine plumbing itself is exactly what step 4 needed to prove out."""
from __future__ import annotations

from salva_core.resolvers.entity_resolution import (
    make_ephemeral_resolver,
    resolve_duplicate_entities,
)
from salva_core.schemas import CanonicalEntity, EvidenceItem


def _company(entity_id: str, title: str, **overrides) -> CanonicalEntity:
    defaults = dict(entity_id=entity_id, entity_type="company", title=title)
    defaults.update(overrides)
    return CanonicalEntity(**defaults)


def test_near_duplicate_names_merge() -> None:
    entities = [
        _company("c1", "Acme Robotics Inc", source_urls=["https://acme.example/about"]),
        _company("c2", "Acme Robotics Incorporated", source_urls=["https://acme.example/contact"]),
    ]
    merged = resolve_duplicate_entities(entities)
    assert len(merged) == 1
    assert sorted(merged[0].source_urls) == [
        "https://acme.example/about",
        "https://acme.example/contact",
    ]


def test_unrelated_entities_stay_separate() -> None:
    entities = [
        _company("c1", "Acme Robotics Inc"),
        _company("c2", "Totally Different Manufacturing Co"),
    ]
    merged = resolve_duplicate_entities(entities)
    assert len(merged) == 2


def test_different_entity_types_never_compared_even_if_similar_names() -> None:
    """A person and a company can coincidentally share a name-like string --
    must never be merged, and must not even trigger a cross-schema
    nomenklatura.matching call (which would be meaningless)."""
    entities = [
        _company("c1", "Acme Robotics"),
        CanonicalEntity(entity_id="p1", entity_type="person", title="Acme Robotics"),
    ]
    merged = resolve_duplicate_entities(entities)
    assert len(merged) == 2


def test_three_way_merge_unions_all_source_urls_and_tags() -> None:
    entities = [
        _company("c1", "Acme Robotics Inc", source_urls=["https://a.example"], tags=["hardware"]),
        _company(
            "c2", "Acme Robotics Incorporated", source_urls=["https://b.example"], tags=["b2b"]
        ),
        _company("c3", "Acme Robotics Inc.", source_urls=["https://c.example"], tags=["robotics"]),
    ]
    merged = resolve_duplicate_entities(entities)
    assert len(merged) == 1
    assert set(merged[0].source_urls) == {
        "https://a.example", "https://b.example", "https://c.example"
    }
    assert set(merged[0].tags) == {"hardware", "b2b", "robotics"}


def test_merge_never_drops_evidence_or_unknown_attributes() -> None:
    entities = [
        _company(
            "c1", "Acme Robotics Inc",
            evidence=[EvidenceItem(source_url="https://a.example", snippet="first claim")],
            attributes={"only_on_first": "kept"},
        ),
        _company(
            "c2", "Acme Robotics Incorporated",
            evidence=[EvidenceItem(source_url="https://b.example", snippet="second claim")],
            attributes={"only_on_second": "kept"},
        ),
    ]
    merged = resolve_duplicate_entities(entities)
    assert len(merged) == 1
    snippets = {item.snippet for item in merged[0].evidence}
    assert snippets == {"first claim", "second claim"}
    assert merged[0].attributes["only_on_first"] == "kept"
    assert merged[0].attributes["only_on_second"] == "kept"


def test_single_or_empty_list_short_circuits_without_a_resolver() -> None:
    assert resolve_duplicate_entities([]) == []
    single = [_company("c1", "Acme Robotics Inc")]
    assert resolve_duplicate_entities(single) == single


def test_resolver_records_positive_judgement_for_merged_pair() -> None:
    resolver = make_ephemeral_resolver()
    entities = [
        _company("c1", "Acme Robotics Inc"),
        _company("c2", "Acme Robotics Incorporated"),
    ]
    resolve_duplicate_entities(entities, resolver=resolver)
    assert resolver.get_canonical("c1") == resolver.get_canonical("c2")
