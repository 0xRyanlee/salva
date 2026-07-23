"""Salva 的 CanonicalEntity 與 FollowTheMoney EntityProxy 之間的雙向轉換。

屬於 Nomenklatura entity-resolution 整合的一部分（見
experiments/salva_v2/ENTITY_RESOLUTION_INTEGRATION_EVAL.md，step 2）。本
模組只做 schema 轉換——不呼叫 nomenklatura.Resolver，也還沒接進 live
pipeline。

Salva 的 entity_type 是扁平 7 值 Literal；FtM 有約 70 種階層 schemata，
Salva 有幾個型別找不到精確對應。以下映射選最接近的既有 schema，而非自訂
FtM schemata（延後——見 eval doc「不做」清單）。每個選中的 schema 都支援
name/sourceUrl/notes/keywords，所以映射是一致的；未來若新增 entity_type，
要確認目標 schema 也支援這四個屬性，或擴充 _to_context_extras()。

Round-trip 完整性：entity_type、confidence、score、status、market、
industry、event、created_at/updated_at，以及完整原始 attributes dict，
在這六種目標 schema 上都沒有通用的 FtM schema 屬性可對應，所以放進
EntityProxy.context（FtM 本來就會透過 to_dict()/get_proxy() 一起round-trip
的 dict，不是 schema 屬性）而不是靜默丟掉。attributes 裡真的對得上目標
schema 屬性的 key，額外多寫一份 FtM property，方便下游 FtM 工具互通。
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
    # 決定 proxy.caption 的屬性是 schema 各自不同的——例如 Document 的
    # caption 優先序是 ["fileName", "title"]，不是 "name"（即使 Document
    # 剛好也有一個不相關的 "name" 屬性）。用錯 key 會讓 caption 靜默變空，
    # 退回 schema 標籤（"File"）而非 entity.title。
    title_property = schema_obj.caption[0] if schema_obj.caption else "name"

    properties: dict[str, list[str]] = {title_property: [entity.title]}
    if entity.source_urls:
        properties["sourceUrl"] = list(entity.source_urls)
    if entity.summary:
        properties["notes"] = [entity.summary]
    if entity.tags:
        properties["keywords"] = list(entity.tags)

    # 盡力做到 FtM 互通：attribute key 對得上這個 schema 真實屬性的，額外
    # 多寫一份成該屬性（加上下面逐字保底存一份，兩邊都不會遺失）——除非這
    # 個 key 上面已經填過了，否則任意 attribute 會蓋掉剛從專屬
    # CanonicalEntity 欄位算出來的 title/sourceUrl。
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
