from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from hashlib import md5
from urllib.parse import urlparse

from core.types import Intent as LegacyIntent
from core.types import SearchTelemetry as LegacyTelemetry
from core.types import UnifiedResult as LegacyUnifiedResult

from .schemas import (
    CanonicalEntity,
    CanonicalRelation,
    EntityType,
    DiscoveryIntent,
    EvidenceItem,
    EventDetails,
    TelemetryRecord,
)


def legacy_intent_to_discovery_intent(intent: LegacyIntent) -> DiscoveryIntent:
    primary = intent.primary_terms[0] if intent.primary_terms else None
    product = primary if primary and " " not in primary else None

    return DiscoveryIntent(
        market=intent.region or "global",
        industry=intent.domain,
        product=product,
        role=intent.roles[0] if intent.roles else None,
        extra_keywords=intent.primary_terms[1:],
        negative_keywords=intent.negative_terms,
        constraints=intent.constraints,
    )


def legacy_result_to_entity(result: LegacyUnifiedResult, market: str | None = None) -> CanonicalEntity:
    entity_type = _infer_entity_type(result)
    raw_evidence = result.raw_evidence or _build_raw_evidence(result)
    evidence = [
        EvidenceItem(
            source_url=result.source_url,
            source_name=result.source_name,
            title=result.title or None,
            snippet=result.description or None,
            captured_at=result.discovered_at,
            metadata={
                "query_used": result.query_used,
                "strategy_used": result.strategy_used,
                "external_id": result.external_id,
                "raw_evidence": raw_evidence,
            },
        )
    ]

    event_details = _build_event_details(result)
    attributes = {
        "description": result.description,
        "ai_type": result.ai_type,
        "ai_summary": result.ai_summary,
        "ai_tags": result.ai_tags,
        "ai_language": result.ai_language,
        "ai_target_audience": result.ai_target_audience,
        "reject_reasons": result.reject_reasons,
        "round_num": result.round_num,
        "query_used": result.query_used,
        "strategy_used": result.strategy_used,
        "raw_evidence": raw_evidence,
    }

    return CanonicalEntity(
        entity_id=_entity_id(result.source_name, result.source_url),
        entity_type=entity_type,
        title=result.title,
        summary=result.ai_summary or result.description or None,
        market=market,
        tags=_merge_tags(result.tags, result.ai_tags),
        source_urls=[result.source_url],
        evidence=evidence,
        confidence=result.relevance_score,
        score=result.relevance_score,
        status="qualified" if result.qualified else "rejected",
        event=event_details,
        created_at=result.discovered_at,
        updated_at=datetime.now(UTC),
        attributes=_drop_none(attributes),
    )


def legacy_result_relations(result: LegacyUnifiedResult) -> list[CanonicalRelation]:
    entity_id = _entity_id(result.source_name, result.source_url)
    relations: list[CanonicalRelation] = []

    if result.organizer_domain:
        relations.append(
            CanonicalRelation(
                relation_id=_relation_id(entity_id, "hosted_by", result.organizer_domain),
                relation_type="hosted_by",
                from_entity_id=entity_id,
                to_entity_id=_entity_id("domain", result.organizer_domain),
                confidence=0.7,
                attributes={"domain": result.organizer_domain},
            )
        )

    if result.organizer_email:
        relations.append(
            CanonicalRelation(
                relation_id=_relation_id(entity_id, "has_contact", result.organizer_email),
                relation_type="has_contact",
                from_entity_id=entity_id,
                to_entity_id=_entity_id("email", result.organizer_email),
                confidence=0.8,
                attributes={"email": result.organizer_email},
            )
        )

    return relations


def legacy_telemetry_to_record(telemetry: LegacyTelemetry) -> TelemetryRecord:
    return TelemetryRecord(
        query=telemetry.query,
        round_num=telemetry.round_num,
        strategy=telemetry.strategy,
        results_total=telemetry.results_total,
        results_qualified=telemetry.results_qualified,
        avg_score=telemetry.avg_score,
        reject_reasons=telemetry.reject_reasons,
        noise_domains=telemetry.noise_domains,
        metadata=getattr(telemetry, "metadata", {}),
    )


def _infer_entity_type(result: LegacyUnifiedResult) -> EntityType:
    if result.starts_at or result.ends_at:
        return "event"
    if result.organizer_email or result.organizer_domain:
        return "lead"
    return "activity_signal"


def _entity_id(namespace: str, value: str) -> str:
    digest = md5(f"{namespace}:{value}".encode(), usedforsecurity=False).hexdigest()
    return f"{namespace}:{digest}"


def _relation_id(left: str, relation: str, right: str) -> str:
    digest = md5(f"{left}:{relation}:{right}".encode(), usedforsecurity=False).hexdigest()
    return f"rel:{digest}"


def _merge_tags(primary: list[str], secondary: list[str]) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for tag in [*primary, *secondary]:
        normalized = tag.strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            merged.append(normalized)
    return merged


def _drop_none(values: Mapping[str, object | None]) -> dict[str, object]:
    return {key: value for key, value in values.items() if value is not None}


def _build_raw_evidence(result: LegacyUnifiedResult) -> dict[str, object]:
    return {
        "raw": {
            "source_name": result.source_name,
            "source_url": result.source_url,
            "external_id": result.external_id,
            "title": result.title,
            "description": result.description,
            "tags": list(result.tags),
        },
        "normalized": {
            "source_url": result.source_url,
            "title": result.title,
            "description": result.description,
        },
        "classification": {
            "entity_type": _infer_entity_type(result),
            "source_domain": result.organizer_domain,
            "has_contact": bool(result.organizer_email),
            "has_schedule": bool(result.starts_at or result.ends_at),
        },
        "dedupe_key": _entity_id(result.source_name, result.source_url),
        "prefilter_reason": None,
    }


def _build_event_details(result: LegacyUnifiedResult) -> EventDetails | None:
    if not any(
        [
            result.starts_at,
            result.ends_at,
            result.timezone,
            result.location_name,
            result.location_address,
            result.city,
            result.country,
            result.latitude,
            result.longitude,
            result.organizer_name,
            result.organizer_email,
            result.organizer_domain,
            result.capacity,
            result.price_amount,
            result.currency,
            result.cover_image_url,
        ]
    ):
        return None
    return EventDetails(
        starts_at=result.starts_at,
        ends_at=result.ends_at,
        timezone=result.timezone,
        location_name=result.location_name,
        location_address=result.location_address,
        city=result.city,
        country=result.country,
        latitude=result.latitude,
        longitude=result.longitude,
        organizer_name=result.organizer_name,
        organizer_email=result.organizer_email,
        organizer_domain=result.organizer_domain,
        capacity=result.capacity,
        price_amount=result.price_amount,
        currency=result.currency,
        cover_image_url=result.cover_image_url,
        speaker_names=[],
    )
