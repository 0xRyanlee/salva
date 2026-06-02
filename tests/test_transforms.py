from salva_core.schemas import CanonicalEntity, EventDetails, TransformOptions
from salva_core.transforms import transform_entities


def test_transform_crm_contact_profile() -> None:
    entity = CanonicalEntity(
        entity_id="lead:1",
        entity_type="lead",
        title="Example Reseller",
        market="Germany",
        industry="software",
        summary="Software reseller summary",
        score=0.81,
        confidence=0.82,
        status="qualified",
        source_urls=["https://example.com"],
        tags=["software", "reseller"],
        attributes={
            "organizer_domain": "example.com",
            "organizer_email": "sales@example.com",
        },
    )

    rows = transform_entities([entity], "crm_contact", TransformOptions())

    assert rows[0]["account_name"] == "Example Reseller"
    assert rows[0]["email"] == "sales@example.com"
    assert rows[0]["lead_score"] == 0.81


def test_transform_with_field_filter_and_rename() -> None:
    entity = CanonicalEntity(
        entity_id="lead:1",
        entity_type="lead",
        title="Example Reseller",
        market="Germany",
        score=0.81,
        source_urls=["https://example.com"],
        attributes={"organizer_domain": "example.com"},
    )

    rows = transform_entities(
        [entity],
        "lead",
        TransformOptions(
            fields=["lead_name", "domain", "score"],
            rename={"lead_name": "name"},
        ),
    )

    assert rows[0] == {
        "name": "Example Reseller",
        "domain": "example.com",
        "score": 0.81,
    }


def test_transform_event_profile_uses_event_submodel() -> None:
    entity = CanonicalEntity(
        entity_id="event:1",
        entity_type="event",
        title="Example Expo",
        summary="Trade show summary",
        score=0.92,
        source_urls=["https://example.com/expo"],
        event=EventDetails(
            city="Taipei",
            location_name="Taipei Nangang",
            starts_at=None,
            ends_at=None,
            organizer_name="Expo Org",
        ),
    )

    rows = transform_entities([entity], "event", TransformOptions())

    assert rows[0]["city"] == "Taipei"
    assert rows[0]["location_name"] == "Taipei Nangang"
    assert rows[0]["organizer_name"] == "Expo Org"
