from core.query_strategy import build_negative_terms, build_query_family
from core.types import Intent, KeywordNode


def test_negative_terms_deduplicate_and_cap() -> None:
    intent = Intent(
        domain="events",
        primary_terms=["workshop"],
        negative_terms=["blog", "news", "blog", "custom"],
    )

    terms = build_negative_terms(intent, limit=4)

    assert terms == ["blog", "news", "custom", "museum"]


def test_query_family_builds_strategy_specific_queries() -> None:
    intent = Intent(
        domain="bd_leads",
        primary_terms=["software reseller"],
        region="Germany",
    )
    nodes = [
        KeywordNode("software reseller", "primary", weight=1.0),
        KeywordNode("Germany", "region", weight=0.7),
        KeywordNode("dealer", "signal", weight=0.4),
    ]

    family = build_query_family(
        intent,
        nodes,
        round_num=2,
        strategy="dive",
        max_queries=6,
    )

    assert family.strategy == "dive"
    assert family.content_weights["title"] > family.content_weights["platform"]
    assert family.source_hints
    assert any("filetype:pdf" in query for query in family.queries)
