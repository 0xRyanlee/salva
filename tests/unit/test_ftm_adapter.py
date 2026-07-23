"""Round-trip contract for the Nomenklatura/FollowTheMoney adapter
(experiments/salva_v2/ENTITY_RESOLUTION_INTEGRATION_EVAL.md, step 6):
CanonicalEntity -> EntityProxy -> CanonicalEntity must be lossless on the
core fields, and non-schema-recognized attribute keys must not silently
vanish (they are asserted present in EntityProxy.context, not just dropped)."""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from salva_core.resolvers.ftm_adapter import (
    ENTITY_TYPE_TO_SCHEMA,
    canonical_entity_to_proxy,
    proxy_to_canonical_entity,
)
from salva_core.schemas import CanonicalEntity
from salva_core.schemas.enums import EntityType


def _make_entity(entity_type: EntityType, **overrides) -> CanonicalEntity:
    defaults = dict(
        entity_id=f"ent:{entity_type}:1",
        entity_type=entity_type,
        title="Acme Robotics Inc",
        summary="A robotics company.",
        market="Germany",
        industry="robotics",
        tags=["b2b", "hardware"],
        source_urls=["https://acme.example/about", "https://acme.example/contact"],
        confidence=0.82,
        score=0.91,
        status="qualified",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 2, tzinfo=UTC),
        attributes={"not_an_ftm_property_xyz": "kept anyway"},
    )
    defaults.update(overrides)
    return CanonicalEntity(**defaults)


@pytest.mark.parametrize("entity_type", list(ENTITY_TYPE_TO_SCHEMA.keys()))
def test_round_trip_preserves_core_fields(entity_type: EntityType) -> None:
    original = _make_entity(entity_type)
    proxy = canonical_entity_to_proxy(original)
    restored = proxy_to_canonical_entity(proxy)

    assert restored.entity_id == original.entity_id
    assert restored.entity_type == original.entity_type
    assert restored.title == original.title
    assert sorted(restored.source_urls) == sorted(original.source_urls)
    assert restored.confidence == original.confidence
    assert sorted(restored.tags) == sorted(original.tags)
    assert restored.attributes == original.attributes


def test_proxy_schema_matches_mapping_table() -> None:
    for entity_type, schema_name in ENTITY_TYPE_TO_SCHEMA.items():
        proxy = canonical_entity_to_proxy(_make_entity(entity_type))
        assert proxy.schema.name == schema_name


def test_attribute_keys_never_silently_disappear() -> None:
    """A key with no matching FtM schema property must still survive via
    context -- proven here by a full round trip, not just presence-checking
    the intermediate proxy (which would pass even if proxy_to_canonical_entity
    forgot to read it back)."""
    entity = _make_entity("company", attributes={"totally_unknown_key_123": "value"})
    proxy = canonical_entity_to_proxy(entity)
    restored = proxy_to_canonical_entity(proxy)
    assert restored.attributes["totally_unknown_key_123"] == "value"


def test_schema_recognized_attribute_is_also_written_as_real_property() -> None:
    """Attribute keys that collide with a real FtM property name (e.g. this
    schema's own "name") get double-written: once into salva_extras for
    lossless round-trip, once as an actual FtM property for downstream FtM
    tool interop."""
    entity = _make_entity("company", attributes={"country": "DE"})
    proxy = canonical_entity_to_proxy(entity)
    assert proxy.get("country") == ["DE"]
    restored = proxy_to_canonical_entity(proxy)
    assert restored.attributes["country"] == "DE"


def test_proxy_without_salva_context_raises_not_silently_guesses() -> None:
    from followthemoney import model

    bare_proxy = model.get_proxy(
        {"id": "external", "schema": "Company", "properties": {"name": ["X"]}}
    )
    with pytest.raises(ValueError, match="salva_entity_type"):
        proxy_to_canonical_entity(bare_proxy)
