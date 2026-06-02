from __future__ import annotations

from typing import Any

from salva_core.schemas import (
    CanonicalEntity,
    OutputProfile,
    OutputTransformCatalog,
    OutputTransformFieldSpec,
    OutputTransformProfileSpec,
    TransformOptions,
)


def transform_entities(
    entities: list[CanonicalEntity],
    output_profile: OutputProfile,
    options: TransformOptions,
) -> list[dict[str, Any]]:
    profile_rows = [_apply_profile(entity, output_profile) for entity in entities]
    return [_apply_options(row, options) for row in profile_rows]


def _apply_profile(entity: CanonicalEntity, output_profile: OutputProfile) -> dict[str, Any]:
    if output_profile == "crm_contact":
        return {
            "account_name": entity.title,
            "market": entity.market,
            "industry": entity.industry,
            "lead_score": entity.score,
            "status": entity.status,
            "domain": _resolve_value(entity, "organizer_domain"),
            "email": _resolve_value(entity, "organizer_email"),
            "summary": entity.summary,
            "source_url": entity.source_urls[0] if entity.source_urls else None,
            "tags": entity.tags,
        }

    if output_profile == "event":
        return {
            "event_name": entity.title,
            "summary": entity.summary,
            "city": _resolve_value(entity, "city"),
            "location_name": _resolve_value(entity, "location_name"),
            "starts_at": _resolve_value(entity, "starts_at"),
            "ends_at": _resolve_value(entity, "ends_at"),
            "organizer_name": _resolve_value(entity, "organizer_name"),
            "source_url": entity.source_urls[0] if entity.source_urls else None,
            "score": entity.score,
            "tags": entity.tags,
        }

    if output_profile == "company_profile":
        return {
            "company_name": entity.title,
            "market": entity.market,
            "industry": entity.industry,
            "summary": entity.summary,
            "domain": _resolve_value(entity, "organizer_domain"),
            "email": _resolve_value(entity, "organizer_email"),
            "confidence": entity.confidence,
            "score": entity.score,
            "source_urls": entity.source_urls,
            "tags": entity.tags,
        }

    if output_profile == "company":
        return {
            "title": entity.title,
            "market": entity.market,
            "industry": entity.industry,
            "summary": entity.summary,
            "domain": _resolve_value(entity, "organizer_domain"),
            "source_urls": entity.source_urls,
            "score": entity.score,
        }

    if output_profile == "activity_signal":
        return {
            "signal_title": entity.title,
            "summary": entity.summary,
            "market": entity.market,
            "score": entity.score,
            "source_url": entity.source_urls[0] if entity.source_urls else None,
            "tags": entity.tags,
        }

    return {
        "lead_name": entity.title,
        "market": entity.market,
        "industry": entity.industry,
        "summary": entity.summary,
        "email": _resolve_value(entity, "organizer_email"),
        "domain": _resolve_value(entity, "organizer_domain"),
        "score": entity.score,
        "confidence": entity.confidence,
        "status": entity.status,
        "source_url": entity.source_urls[0] if entity.source_urls else None,
        "tags": entity.tags,
    }


def _apply_options(row: dict[str, Any], options: TransformOptions) -> dict[str, Any]:
    result = dict(row)

    if options.fields:
        result = {key: result.get(key) for key in options.fields if key in result}

    if options.rename:
        renamed: dict[str, Any] = {}
        for key, value in result.items():
            renamed[options.rename.get(key, key)] = value
        result = renamed

    if options.drop_nulls:
        result = {key: value for key, value in result.items() if value is not None}

    return result


def build_output_transform_catalog() -> OutputTransformCatalog:
    items = [
        OutputTransformProfileSpec(
            profile="lead",
            description="Default lead-oriented output for outreach and qualification workflows.",
            caller_types=["human", "agent", "crm"],
            fields=[
                OutputTransformFieldSpec(name="lead_name", source="entity.title", description="Lead or contact name.", required=True, examples=["Acme Software GmbH"]),
                OutputTransformFieldSpec(name="market", source="entity.market", description="Target market or region."),
                OutputTransformFieldSpec(name="industry", source="entity.industry", description="Target industry or vertical."),
                OutputTransformFieldSpec(name="summary", source="entity.summary", description="Short summary of the lead."),
                OutputTransformFieldSpec(name="email", source="entity.attributes.organizer_email", description="Contact email when available."),
                OutputTransformFieldSpec(name="domain", source="entity.attributes.organizer_domain", description="Contact or organization domain."),
                OutputTransformFieldSpec(name="score", source="entity.score", description="Ranking or qualification score."),
                OutputTransformFieldSpec(name="confidence", source="entity.confidence", description="Extraction / canonicalization confidence."),
                OutputTransformFieldSpec(name="status", source="entity.status", description="Lifecycle status for downstream workflows."),
                OutputTransformFieldSpec(name="source_url", source="entity.source_urls[0]", description="Primary supporting source URL."),
                OutputTransformFieldSpec(name="tags", source="entity.tags", description="Derived tags."),
            ],
            notes=["Optimized for outreach, CRM sync, and human review."],
        ),
        OutputTransformProfileSpec(
            profile="crm_contact",
            description="CRM-friendly contact record with account-oriented naming.",
            caller_types=["human", "agent", "crm"],
            fields=[
                OutputTransformFieldSpec(name="account_name", source="entity.title", description="CRM account or contact name.", required=True),
                OutputTransformFieldSpec(name="market", source="entity.market", description="Target market or region."),
                OutputTransformFieldSpec(name="industry", source="entity.industry", description="Target industry or vertical."),
                OutputTransformFieldSpec(name="lead_score", source="entity.score", description="Lead score for CRM routing."),
                OutputTransformFieldSpec(name="status", source="entity.status", description="CRM lifecycle status."),
                OutputTransformFieldSpec(name="domain", source="entity.attributes.organizer_domain", description="Primary domain."),
                OutputTransformFieldSpec(name="email", source="entity.attributes.organizer_email", description="Primary email."),
                OutputTransformFieldSpec(name="summary", source="entity.summary", description="Brief summary."),
                OutputTransformFieldSpec(name="source_url", source="entity.source_urls[0]", description="Primary source URL."),
                OutputTransformFieldSpec(name="tags", source="entity.tags", description="Derived tags."),
            ],
            notes=["Use when the caller expects CRM-style field naming."],
        ),
        OutputTransformProfileSpec(
            profile="event",
            description="Event-oriented record for schedules, venues, and organizers.",
            caller_types=["human", "agent", "event"],
            fields=[
                OutputTransformFieldSpec(name="event_name", source="entity.title", description="Event title.", required=True),
                OutputTransformFieldSpec(name="summary", source="entity.summary", description="Event summary."),
                OutputTransformFieldSpec(name="city", source="entity.event.city", description="Event city."),
                OutputTransformFieldSpec(name="location_name", source="entity.event.location_name", description="Venue or location name."),
                OutputTransformFieldSpec(name="starts_at", source="entity.event.starts_at", description="Start timestamp."),
                OutputTransformFieldSpec(name="ends_at", source="entity.event.ends_at", description="End timestamp."),
                OutputTransformFieldSpec(name="organizer_name", source="entity.event.organizer_name", description="Organizer name."),
                OutputTransformFieldSpec(name="source_url", source="entity.source_urls[0]", description="Primary source URL."),
                OutputTransformFieldSpec(name="score", source="entity.score", description="Ranking score."),
                OutputTransformFieldSpec(name="tags", source="entity.tags", description="Derived tags."),
            ],
            notes=["Use for event discovery and schedule extraction."],
        ),
        OutputTransformProfileSpec(
            profile="activity_signal",
            description="Compact weak-signal output for market activity and signal routing.",
            caller_types=["human", "agent", "analytics"],
            fields=[
                OutputTransformFieldSpec(name="signal_title", source="entity.title", description="Signal title.", required=True),
                OutputTransformFieldSpec(name="summary", source="entity.summary", description="Signal summary."),
                OutputTransformFieldSpec(name="market", source="entity.market", description="Target market or region."),
                OutputTransformFieldSpec(name="score", source="entity.score", description="Signal score."),
                OutputTransformFieldSpec(name="source_url", source="entity.source_urls[0]", description="Primary source URL."),
                OutputTransformFieldSpec(name="tags", source="entity.tags", description="Derived tags."),
            ],
            notes=["Use when the caller wants short, weak-signal oriented output."],
        ),
        OutputTransformProfileSpec(
            profile="company_profile",
            description="Company profile output with source lineage preserved.",
            caller_types=["human", "agent", "analytics"],
            fields=[
                OutputTransformFieldSpec(name="company_name", source="entity.title", description="Company name.", required=True),
                OutputTransformFieldSpec(name="market", source="entity.market", description="Target market or region."),
                OutputTransformFieldSpec(name="industry", source="entity.industry", description="Target industry or vertical."),
                OutputTransformFieldSpec(name="summary", source="entity.summary", description="Short summary."),
                OutputTransformFieldSpec(name="domain", source="entity.attributes.organizer_domain", description="Primary domain."),
                OutputTransformFieldSpec(name="email", source="entity.attributes.organizer_email", description="Primary email."),
                OutputTransformFieldSpec(name="confidence", source="entity.confidence", description="Extraction confidence."),
                OutputTransformFieldSpec(name="score", source="entity.score", description="Ranking score."),
                OutputTransformFieldSpec(name="source_urls", source="entity.source_urls", description="Supporting source URLs."),
                OutputTransformFieldSpec(name="tags", source="entity.tags", description="Derived tags."),
            ],
            notes=["Use for company research and profile export."],
        ),
        OutputTransformProfileSpec(
            profile="company",
            description="Simplified company output for lightweight consumers.",
            caller_types=["human", "agent", "analytics"],
            fields=[
                OutputTransformFieldSpec(name="title", source="entity.title", description="Company title.", required=True),
                OutputTransformFieldSpec(name="market", source="entity.market", description="Target market or region."),
                OutputTransformFieldSpec(name="industry", source="entity.industry", description="Target industry or vertical."),
                OutputTransformFieldSpec(name="summary", source="entity.summary", description="Short summary."),
                OutputTransformFieldSpec(name="domain", source="entity.attributes.organizer_domain", description="Primary domain."),
                OutputTransformFieldSpec(name="source_urls", source="entity.source_urls", description="Supporting source URLs."),
                OutputTransformFieldSpec(name="score", source="entity.score", description="Ranking score."),
            ],
            notes=["Use when the caller only needs a small company record."],
        ),
    ]
    return OutputTransformCatalog(items=items, total=len(items))


def _resolve_value(entity: CanonicalEntity, field_name: str) -> Any:
    event = getattr(entity, "event", None)
    if event is not None:
        value = getattr(event, field_name, None)
        if value is not None:
            return value
    return entity.attributes.get(field_name)
