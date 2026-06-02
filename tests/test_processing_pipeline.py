from processing.dedup import MemoryDeduplicator
from processing.extractor import BaseExtractor
from processing.pipeline import ProcessingPipeline
from core.types import UnifiedResult


def test_processing_pipeline_normalizes_and_classifies_event_results() -> None:
    pipeline = ProcessingPipeline()
    raw = {
        "url": "https://www.Eventbrite.com/t/%20test-event/?utm_source=foo",
        "title": "  Test   Event  Taipei ",
        "snippet": "Join our meetup and register today!",
        "engine": "searxng",
    }

    processed = pipeline.process(raw, query="test event taipei", strategy="radar")

    assert processed.normalized["title"] == "Test Event Taipei"
    assert processed.normalized["url"] == "https://www.eventbrite.com/t/%20test-event"
    assert processed.classification["content_type"] == "event"
    assert processed.classification["source_kind"] == "site"
    assert processed.dedupe_key


def test_processing_pipeline_prefilters_low_signal_snippets() -> None:
    pipeline = ProcessingPipeline()
    raw = {
        "url": "https://example.com/news",
        "title": "General News Update",
        "snippet": "Today we share general updates and unrelated content.",
        "engine": "searxng",
    }

    accepted, reason = pipeline.prefilter(raw, query="software reseller germany", strategy="dive")

    assert not accepted
    assert reason == "dive_query_mismatch"


def test_extractor_tags_include_classification() -> None:
    extractor = BaseExtractor()
    raw = {
        "url": "https://example.com/company",
        "title": "Example Company About",
        "snippet": "Official company page",
        "engine": "searxng",
    }

    result = extractor.extract(raw, query="example company", round_num=1, strategy="dive")

    assert result is not None
    assert "company" in result.tags
    assert "site" in result.tags
    assert result.raw_evidence["classification"]["content_type"] == "company"


def test_memory_deduplicator_uses_stable_keys() -> None:
    deduplicator = MemoryDeduplicator()
    first = UnifiedResult(
        source_name="searxng",
        source_url="https://example.com/path/?utm=1",
        title="Example Title",
    )
    second = UnifiedResult(
        source_name="searxng",
        source_url="https://example.com/path",
        title="Example Title",
    )

    assert not deduplicator.is_duplicate(first)
    deduplicator.register(first)
    assert deduplicator.is_duplicate(second)
