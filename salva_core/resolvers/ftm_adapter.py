"""Conversion between Salva's CanonicalEntity and FollowTheMoney EntityProxy.

Part of the Nomenklatura entity-resolution integration (see
experiments/salva_v2/ENTITY_RESOLUTION_INTEGRATION_EVAL.md, step 2). This
module only does the schema translation -- it does not call
nomenklatura.Resolver and is not wired into the live pipeline yet.

Salva's entity_type is a flat 7-value Literal; FtM has ~70 hierarchical
schemata with no precise match for several of Salva's types. The mapping
below picks the closest existing schema rather than defining custom FtM
schemata (deferred -- see the eval doc's "not now" list). Every schema
chosen supports name/sourceUrl/notes/keywords so the mapping below is
uniform; if a future entity_type is added, verify its target schema also
supports those four properties or extend _to_context_extras() accordingly.

Round-trip fidelity: entity_type, confidence, score, status, market,
industry, event, created_at/updated_at, and the full original attributes
dict do not have universal FtM schema properties across all six target
schemata, so they are carried in EntityProxy.context (a dict FtM already
round-trips through to_dict()/get_proxy(), not a schema property) rather
than silently dropped. attributes keys that DO match a real property on the
target schema are additionally written as FtM properties for interop with
downstream FtM tooling.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from followthemoney import model
from followthemoney.proxy import EntityProxy

from salva_core.schemas import CanonicalEntity
from salva_core.schemas.enums import EntityType

ENTITY_TYPE_TO_SCHEMA: dict[EntityType, str] = {
    "company": "Company",
    "person": "Person",
    "event": "Event",
    "activity_signal": "Event",
    "lead": "LegalEntity",
    "document": "Document",
    "source": "Document",
}

_CONTEXT_KEY = "salva_entity_type"
_EXTRAS_KEY = "salva_extras"


def canonical_entity_to_proxy(entity: CanonicalEntity) -> EntityProxy:
    schema = ENTITY_TYPE_TO_SCHEMA[entity.entity_type]
    schema_obj = model.get(schema)
    schema_props = schema_obj.properties
    # The property that resolves proxy.caption is schema-specific -- e.g.
    # Document's caption priority is ["fileName", "title"], not "name" (even
    # though Document happens to also have an unrelated "name" property).
    # Using the wrong key silently produces an empty caption that falls
    # back to the schema label ("File") instead of entity.title.
    title_property = schema_obj.caption[0] if schema_obj.caption else "name"

    properties: dict[str, list[str]] = {title_property: [entity.title]}
    if entity.source_urls:
        properties["sourceUrl"] = list(entity.source_urls)
    if entity.summary:
        properties["notes"] = [entity.summary]
    if entity.tags:
        properties["keywords"] = list(entity.tags)

    # Best-effort FtM interop: attribute keys that match a real property on
    # this schema get written as that property too (in addition to the
    # verbatim stash below, so nothing is silently lost either way) --
    # unless that key is one we already populated above, which would
    # otherwise let an arbitrary attribute clobber e.g. the title/sourceUrl
    # we just derived from dedicated CanonicalEntity fields.
    for key, value in entity.attributes.items():
        if key in schema_props and key not in properties and value is not None:
            properties[key] = value if isinstance(value, list) else [str(value)]

    proxy = model.get_proxy({"id": entity.entity_id, "schema": schema, "properties": properties})
    proxy.context[_CONTEXT_KEY] = entity.entity_type
    proxy.context[_EXTRAS_KEY] = {
        "confidence": entity.confidence,
        "score": entity.score,
        "status": entity.status,
        "market": entity.market,
        "industry": entity.industry,
        "created_at": entity.created_at.isoformat() if entity.created_at else None,
        "updated_at": entity.updated_at.isoformat() if entity.updated_at else None,
        "event": entity.event.model_dump(mode="json") if entity.event else None,
        "attributes": entity.attributes,
    }
    return proxy


def proxy_to_canonical_entity(proxy: EntityProxy) -> CanonicalEntity:
    extras: dict[str, Any] = proxy.context.get(_EXTRAS_KEY, {})
    entity_type = proxy.context.get(_CONTEXT_KEY)
    if entity_type is None:
        raise ValueError(
            f"EntityProxy {proxy.id!r} has no {_CONTEXT_KEY!r} in context -- "
            "it was not produced by canonical_entity_to_proxy() and cannot be "
            "converted back losslessly."
        )

    event_data = extras.get("event")
    from salva_core.schemas.entity import EventDetails

    return CanonicalEntity(
        entity_id=proxy.id,
        entity_type=entity_type,
        title=proxy.caption or "",
        summary=_first(proxy.get("notes")),
        market=extras.get("market"),
        industry=extras.get("industry"),
        tags=list(proxy.get("keywords")),
        source_urls=list(proxy.get("sourceUrl")),
        confidence=extras.get("confidence", 0.0),
        score=extras.get("score", 0.0),
        status=extras.get("status", "new"),
        event=EventDetails.model_validate(event_data) if event_data else None,
        created_at=_parse_dt(extras.get("created_at")),
        updated_at=_parse_dt(extras.get("updated_at")),
        attributes=extras.get("attributes", {}),
    )


def _first(values: list[str]) -> str | None:
    return values[0] if values else None


def _parse_dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None
