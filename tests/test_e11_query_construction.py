"""E11 — Query construction fidelity.

VP11: A DiscoveryIntent with brand (product) + role + region must produce
at least one dive query that contains both the brand signal AND the role signal,
not just industry + region.

Root cause in E10: 'role' was added to primary_terms, competing with 'product'
for the top-2 slot — and losing.  After the fix:
  - product → primary node (weight 1.0, always top-ranked)
  - role → role node (weight 0.8) via Intent.roles + _bootstrap()
  - _build_dive_queries() combines primary + role in the first query
"""
from __future__ import annotations

from core.keyword_graph import KeywordGraph
from core.query_strategy import build_queries, build_strategy_profile
from core.types import Intent


def _naturehike_intent() -> Intent:
    return Intent(
        domain="bd_leads",
        primary_terms=["Naturehike", "importer", "wholesale", "retailer"],
        region="Germany",
        roles=["distributor"],
        negative_terms=["blog", "review"],
    )


def _computex_intent() -> Intent:
    return Intent(
        domain="taiwan_hardware",
        primary_terms=["GIGABYTE", "ASUS", "MSI"],
        region="Computex 2026",
        roles=["exhibitor"],
    )


class TestRoleNodeBootstrap:
    def test_role_added_as_role_type_node(self):
        intent = _naturehike_intent()
        graph = KeywordGraph(intent)
        assert "distributor" in graph.nodes
        assert graph.nodes["distributor"].node_type == "role"

    def test_role_weight_higher_than_signal(self):
        intent = _naturehike_intent()
        graph = KeywordGraph(intent)
        role_weight = graph.nodes["distributor"].weight
        # Signal nodes start at 0.4; role nodes start at 0.8
        assert role_weight > 0.4, f"Role weight should be > 0.4, got {role_weight}"

    def test_product_stays_primary(self):
        intent = _naturehike_intent()
        graph = KeywordGraph(intent)
        assert graph.nodes["Naturehike"].node_type == "primary"

    def test_computex_exhibitor_role_node(self):
        intent = _computex_intent()
        graph = KeywordGraph(intent)
        assert "exhibitor" in graph.nodes
        assert graph.nodes["exhibitor"].node_type == "role"


class TestDiveQueryContainsRoleSignal:
    def test_brand_and_role_both_in_dive_query(self):
        intent = _naturehike_intent()
        graph = KeywordGraph(intent)
        nodes = graph._ranked_nodes()
        profile = build_strategy_profile(intent, "dive", 1, graph.vocab)
        queries = build_queries(intent, nodes, round_num=1, strategy="dive",
                                max_queries=6, profile=profile)
        # At least one dive query must contain both the brand and the role
        combined = any(
            "naturehike" in q.lower() and "distributor" in q.lower()
            for q in queries
        )
        assert combined, (
            f"Expected at least one query with both 'Naturehike' and 'distributor'.\n"
            f"Got queries: {queries}"
        )

    def test_region_included_in_top_dive_query(self):
        intent = _naturehike_intent()
        graph = KeywordGraph(intent)
        nodes = graph._ranked_nodes()
        profile = build_strategy_profile(intent, "dive", 1, graph.vocab)
        queries = build_queries(intent, nodes, round_num=1, strategy="dive",
                                max_queries=6, profile=profile)
        # Region "Germany" expands to variants: "DE", "German", "Deutschland"
        germany_variants = {"germany", "de", "german", "deutschland"}
        assert any(
            any(v in q.lower().split() for v in germany_variants)
            for q in queries
        ), (
            f"Expected a Germany region variant (DE/German/Deutschland) in at least one query.\n"
            f"Got queries: {queries}"
        )

    def test_no_role_in_primary_terms_after_fix(self):
        """role must NOT be in primary_terms after the service.py fix."""
        from salva_core.schemas import DiscoveryIntent, DiscoveryRequest
        from salva_core.service import discovery_request_to_legacy_intent
        req = DiscoveryRequest(
            objective="find_leads",
            intent=DiscoveryIntent(
                market="Germany",
                industry="outdoor equipment",
                product="Naturehike",
                role="distributor",
                extra_keywords=["importer"],
            ),
            max_results=20,
        )
        legacy = discovery_request_to_legacy_intent(req)
        # 'distributor' should be in roles, not primary_terms
        assert "distributor" not in legacy.primary_terms, (
            "role must not pollute primary_terms — it should only be in Intent.roles"
        )
        assert "distributor" in legacy.roles

    def test_computex_exhibitor_in_dive_query(self):
        intent = _computex_intent()
        graph = KeywordGraph(intent)
        nodes = graph._ranked_nodes()
        profile = build_strategy_profile(intent, "dive", 1, graph.vocab)
        queries = build_queries(intent, nodes, round_num=1, strategy="dive",
                                max_queries=6, profile=profile)
        assert any("exhibitor" in q.lower() for q in queries), (
            f"Expected 'exhibitor' role in Computex queries. Got: {queries}"
        )


class TestNoRoleBleedIntoAnchorQueries:
    def test_anchor_uses_role_nodes(self):
        intent = _naturehike_intent()
        graph = KeywordGraph(intent)
        nodes = graph._ranked_nodes()
        profile = build_strategy_profile(intent, "anchor", 1, graph.vocab)
        queries = build_queries(intent, nodes, round_num=1, strategy="anchor",
                                max_queries=8, profile=profile)
        # Anchor queries should also include role terms when building combos
        assert any("distributor" in q.lower() for q in queries), (
            f"Anchor queries should use role nodes. Got: {queries}"
        )
