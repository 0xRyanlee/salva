from datetime import UTC, datetime

from core.types import Intent, SearchTelemetry, UnifiedResult
from salva_core.legacy import (
    legacy_intent_to_discovery_intent,
    legacy_result_relations,
    legacy_result_to_entity,
    legacy_telemetry_to_record,
)


def test_legacy_intent_maps_to_discovery_intent() -> None:
    intent = Intent(
        domain="bd_leads",
        primary_terms=["software reseller", "integration"],
        region="Germany",
        roles=["reseller"],
        negative_terms=["blog"],
        constraints={"language": "en"},
    )

    mapped = legacy_intent_to_discovery_intent(intent)

    assert mapped.market == "Germany"
    assert mapped.industry == "bd_leads"
    assert mapped.role == "reseller"
    assert mapped.extra_keywords == ["integration"]
    assert mapped.negative_keywords == ["blog"]


def test_legacy_result_maps_to_canonical_entity_and_relations() -> None:
    result = UnifiedResult(
        source_name="searxng",
        source_url="https://example.com/reseller",
        title="Example Reseller",
        description="Official software reseller in Germany",
        organizer_email="sales@example.com",
        organizer_domain="example.com",
        discovered_at=datetime.now(UTC),
        relevance_score=0.82,
        qualified=True,
        query_used="software reseller germany",
        strategy_used="dive",
    )

    entity = legacy_result_to_entity(result, market="Germany")
    relations = legacy_result_relations(result)

    assert entity.entity_type == "lead"
    assert entity.market == "Germany"
    assert entity.status == "qualified"
    assert entity.source_urls == ["https://example.com/reseller"]
    # E13: contact-only results must NOT produce event details
    assert entity.event is None
    assert entity.evidence[0].metadata["raw_evidence"]["raw"]["title"] == "Example Reseller"
    # organizer_email / organizer_domain captured as relations, not event fields
    assert len(relations) == 2
    relation_types = {r.relation_type for r in relations}
    assert "has_contact" in relation_types
    assert "hosted_by" in relation_types


def test_legacy_telemetry_maps_to_record() -> None:
    telemetry = SearchTelemetry(
        query="software reseller germany",
        round_num=1,
        strategy="dive",
        results_total=10,
        results_qualified=2,
        avg_score=0.7,
        reject_reasons=["no_contact"],
        noise_domains=["reddit.com"],
        metadata={"content_weights": {"title": 0.45}},
    )

    record = legacy_telemetry_to_record(telemetry)

    assert record.query == telemetry.query
    assert record.results_total == 10
    assert record.noise_domains == ["reddit.com"]
    assert record.metadata["content_weights"]["title"] == 0.45
