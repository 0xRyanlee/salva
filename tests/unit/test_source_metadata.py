from retrieval.source_metadata import classify_source_attempt


def test_local_source_is_low_risk_when_successful() -> None:
    metadata = classify_source_attempt("http://localhost:8080", succeeded=True, error=None)
    assert metadata["source_class"] == "local"
    assert metadata["risk_level"] == "low"
    assert metadata["recommended_crawl_mode"] == "normal"


def test_public_failure_escalates_to_wall_guarded() -> None:
    metadata = classify_source_attempt("https://searx.be", succeeded=False, error="timeout")
    assert metadata["source_class"] == "public_mirror"
    assert metadata["risk_level"] == "high"
    assert metadata["recommended_crawl_mode"] == "wall_guarded"
