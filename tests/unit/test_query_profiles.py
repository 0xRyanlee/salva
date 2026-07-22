from core.keyword_graph import KeywordGraph
from core.types import Intent, SearchTelemetry, UnifiedResult
from processing.scorer import QualificationScorer


def test_keyword_graph_exposes_round_content_weights() -> None:
    intent = Intent(
        domain="events",
        primary_terms=["workshop"],
        region="Taipei",
        negative_terms=["job"],
    )

    graph = KeywordGraph(intent)

    dive = graph.next_round_queries(round_num=1, strategy="dive", max_queries=6)
    radar = graph.next_round_queries(round_num=2, strategy="radar", max_queries=10)

    assert dive.content_weights["title"] > dive.content_weights["platform"]
    assert "precision_first" in dive.notes
    assert "facebook.com" in radar.source_hints
    assert radar.content_weights["platform"] > radar.content_weights["title"]
    assert any("site:" in query for query in radar.queries)
    assert any(
        any(f"site:{hint}" in query for hint in radar.source_hints)
        for query in radar.queries
    )


def test_scorer_responds_to_round_profile_context() -> None:
    intent = Intent(
        domain="events",
        primary_terms=["workshop"],
        region="Taipei",
    )
    result = UnifiedResult(
        source_name="searxng",
        source_url="https://example.com/workshop",
        title="Workshop Taipei",
        description="Official workshop page",
        organizer_email="hello@example.com",
        organizer_domain="example.com",
    )
    scorer = QualificationScorer()

    precision = scorer.score(
        result,
        intent,
        context={
            "notes": ["precision_first"],
            "content_weights": {"title": 0.45, "platform": 0.10},
        },
    )
    source_discovery = scorer.score(
        result,
        intent,
        context={
            "notes": ["source_discovery"],
            "content_weights": {"title": 0.20, "platform": 0.40},
        },
    )

    assert precision != source_discovery
    assert source_discovery != 0.0


def test_keyword_graph_telemetry_uses_profile_metadata() -> None:
    intent = Intent(
        domain="events",
        primary_terms=["workshop"],
        region="Taipei",
    )
    graph = KeywordGraph(intent)
    node = graph.nodes["workshop"]
    before = node.weight

    graph.apply_telemetry(
        SearchTelemetry(
            query="workshop Taipei",
            round_num=1,
            strategy="dive",
            results_total=10,
            results_qualified=4,
            metadata={
                "notes": ["precision_first"],
                "content_weights": {"title": 0.45, "platform": 0.10},
            },
        )
    )

    assert graph.nodes["workshop"].weight >= before
    assert graph.nodes["workshop"].source_score >= 0.0
