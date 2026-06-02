"""
Keyword Graph — query intelligence layer for Salva's iterative retrieval loop.

Core loop:
    Seed Terms → Expand → Search → Weighted Scoring → Prune Noise
    → Promote Core Terms → Generate Next Round Queries → repeat

Theory basis:
    Information Retrieval (query expansion, co-occurrence)
    Semantic Networks (synonym/role graph)
    Rocchio Algorithm (relevance feedback)
    SEO Topic Clusters (pillar + supporting keywords)

Domain vocabulary is fully injectable via DomainVocab. No domain is hardcoded
here. The registry in core/domain_vocab.py holds built-in reference implementations;
callers extend them via DomainHints on the request.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Callable

from core.types import Intent, KeywordNode, KeywordEdge, QueryFamily, SearchTelemetry
from core.domain_vocab import DomainVocab, get_vocab
from core.query_strategy import build_query_family, build_strategy_profile

logger = logging.getLogger("salva.keyword_graph")


class KeywordGraph:
    """
    In-memory graph of KeywordNodes + KeywordEdges.

    Bootstrap order:
        1. Primary terms from intent  (weight 1.0)
        2. Synonym/role expansions from DomainVocab  (weight 0.6)
        3. Region variant nodes  (weight 0.7)
        4. Signal term nodes  (weight 0.4)
        5. seed_from_memory() — cross-run learning (weight 0.5, type "memory")

    Rounds
    ------
    Each next_round_queries() call generates a QueryFamily and updates node
    weights from the previous round's telemetry (Rocchio-style feedback).
    """

    def __init__(
        self,
        intent: Intent,
        vocab: DomainVocab | None = None,
        persist_path: Path | None = None,
        expand_fn: Callable[[str, str], list[str]] | None = None,
    ):
        self.intent = intent
        # Resolved vocab: explicit injection > registry lookup > general fallback
        self.vocab = vocab if vocab is not None else get_vocab(intent.domain)
        self.persist_path = persist_path
        self.expand_fn = expand_fn

        self.nodes: dict[str, KeywordNode] = {}
        self.edges: list[KeywordEdge] = []

        if persist_path and persist_path.exists():
            self._load(persist_path)
        else:
            self._bootstrap()

    # ------------------------------------------------------------------
    # Bootstrap
    # ------------------------------------------------------------------

    def _bootstrap(self) -> None:
        vocab = self.vocab

        # Seed primary terms — highest weight, never pruned
        for term in self.intent.primary_terms:
            self._add_node(term, "primary", weight=1.0)

        # Synonym and role expansions
        for canonical, variants in vocab.synonym_groups.items():
            if canonical in self.nodes:
                for v in variants:
                    self._add_node(v, "synonym", weight=0.6)
                    self._add_edge(canonical, v, "synonym")

        # Region expansion
        if self.intent.region:
            region_vars = vocab.region_variants
            for v in region_vars.get(self.intent.region, [self.intent.region]):
                self._add_node(v, "region", weight=0.7)

        # Signal terms (cap at 12 to keep graph manageable)
        for sig in vocab.signal_terms[:12]:
            self._add_node(sig, "signal", weight=0.4)

    # ------------------------------------------------------------------
    # Cross-run memory seeding (A3)
    # ------------------------------------------------------------------

    def seed_from_memory(
        self,
        memory_reader: Callable[[str, int], list[dict[str, Any]]],
        top_k: int = 5,
        seed_weight: float = 0.5,
    ) -> int:
        """
        Inject high-scoring phrases from past successful query families.

        memory_reader is a callable so KeywordGraph stays independent of
        the persistence layer. Inject via service.py.

        Args:
            memory_reader: fn(domain, top_k) → list of {"source_nodes": [...], "success_score": float}
            top_k: maximum number of past families to read
            seed_weight: initial weight for injected nodes (below primary=1.0)

        Returns:
            Number of new nodes injected.
        """
        injected = 0
        try:
            records = memory_reader(self.intent.domain, top_k)
        except Exception as exc:
            logger.warning("seed_from_memory: reader failed (%s), skipping", exc)
            return 0

        seen_phrases: set[str] = set(self.nodes.keys())
        for record in records:
            for phrase in record.get("source_nodes", []):
                phrase = phrase.strip()
                if not phrase or phrase in seen_phrases:
                    continue
                self._add_node(phrase, "memory", weight=seed_weight)
                seen_phrases.add(phrase)
                injected += 1

        if injected:
            logger.debug("seed_from_memory: injected %d nodes from past runs", injected)
        return injected

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def next_round_queries(
        self,
        round_num: int,
        strategy: str = "dive",
        max_queries: int = 10,
    ) -> QueryFamily:
        nodes = self._ranked_nodes()
        profile = build_strategy_profile(self.intent, strategy, round_num, self.vocab)
        queries = build_query_family(
            self.intent,
            nodes,
            round_num,
            strategy,
            max_queries=max_queries,
            profile=profile,
        ).queries
        source_nodes = [n.phrase for n in nodes[:5]]
        return QueryFamily(
            round_num=round_num,
            queries=queries,
            strategy=strategy,
            source_nodes=source_nodes,
            content_weights=profile["content_weights"],
            source_hints=profile["source_hints"],
            notes=profile["notes"],
        )

    def apply_telemetry(self, telemetry: SearchTelemetry) -> None:
        """
        Rocchio-style feedback: amplify high-hit nodes, dampen noise-linked nodes.

        new_weight = old_weight + α * hit_rate * multiplier - β * noise_rate
        """
        profile = telemetry.metadata or {}
        notes = set(profile.get("notes", [])) if isinstance(profile, dict) else set()
        content_weights = profile.get("content_weights", {}) if isinstance(profile, dict) else {}

        if "precision_first" in notes:
            alpha, beta = 0.38, 0.08
        elif "graph_expansion" in notes:
            alpha, beta = 0.30, 0.14
        elif "source_discovery" in notes:
            alpha, beta = 0.24, 0.18
        else:
            alpha, beta = 0.30, 0.15

        hit_rate = (
            telemetry.results_qualified / telemetry.results_total
            if telemetry.results_total > 0 else 0.0
        )
        noise_rate = len(telemetry.noise_domains) / max(telemetry.results_total, 1)
        type_multipliers = {
            "primary": float(content_weights.get("title",    0.25) or 0.25),
            "synonym": float(content_weights.get("snippet",  0.25) or 0.25),
            "role":    float(content_weights.get("document", 0.20) or 0.20),
            "region":  float(content_weights.get("document", 0.20) or 0.20),
            "signal":  float(content_weights.get("platform", 0.10) or 0.10),
            "memory":  float(content_weights.get("snippet",  0.20) or 0.20),
        }

        for token in telemetry.query.lower().split():
            if token not in self.nodes:
                continue
            node = self.nodes[token]
            multiplier = type_multipliers.get(node.node_type, 0.2)
            node.weight = min(1.0, max(0.0,
                node.weight + alpha * hit_rate * multiplier - beta * noise_rate
            ))
            node.lead_score = 0.7 * node.lead_score + 0.3 * hit_rate * multiplier
            node.source_score = min(1.0, max(0.0,
                0.8 * node.source_score
                + 0.2 * max(0.0, 1.0 - noise_rate) * multiplier,
            ))

        if self.persist_path:
            self._save(self.persist_path)

    def prune(self, threshold: float = 0.15) -> int:
        before = len(self.nodes)
        self.nodes = {
            k: v for k, v in self.nodes.items()
            # primary nodes are never pruned; memory nodes survive until round 2+
            if v.composite_score() >= threshold or v.node_type == "primary"
        }
        return before - len(self.nodes)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _ranked_nodes(self) -> list[KeywordNode]:
        return sorted(self.nodes.values(), key=lambda n: n.composite_score(), reverse=True)

    def _add_node(self, phrase: str, node_type: str, weight: float = 0.5) -> None:
        if phrase not in self.nodes:
            self.nodes[phrase] = KeywordNode(phrase, node_type, weight)

    def _add_edge(self, src: str, tgt: str, relation: str, w: float = 1.0) -> None:
        self.edges.append(KeywordEdge(src, tgt, relation, w))

    def _save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "nodes": {k: asdict(v) for k, v in self.nodes.items()},
            "edges": [asdict(e) for e in self.edges],
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    def _load(self, path: Path) -> None:
        data = json.loads(path.read_text())
        self.nodes = {k: KeywordNode(**v) for k, v in data.get("nodes", {}).items()}
        self.edges = [KeywordEdge(**e) for e in data.get("edges", [])]
