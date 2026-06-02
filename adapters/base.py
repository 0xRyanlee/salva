"""
Adapter protocol — the only domain-specific layer.

Salva's core (controller, keyword_graph, scorer) is domain-agnostic.
Adapters translate UnifiedResult into the target persistence schema
and handle the actual DB write.

Implementing an adapter:
    1. Subclass BaseAdapter
    2. Implement `persist(results)` to write to your store
    3. Optionally override `enrich_fields(result)` to customize OMLX input
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from core.types import UnifiedResult
from core.controller import RunSummary


class BaseAdapter(ABC):
    domain: str = "base"

    @abstractmethod
    def persist(self, results: list[UnifiedResult]) -> dict:
        """
        Write qualified results to the target store.
        Returns a summary dict: {"inserted": n, "updated": n, "skipped": n}
        """
        ...

    def enrich_fields(self, result: UnifiedResult) -> dict:
        """Map UnifiedResult to OMLX enrichment input fields."""
        return {
            "title": result.title,
            "description": result.description,
            "location": result.location_name or result.location_address or "",
            "starts_at": str(result.starts_at) if result.starts_at else "",
            "price": str(result.price_amount) if result.price_amount else "免費",
            "source_url": result.source_url,
        }

    def on_run_complete(self, summary: RunSummary) -> None:
        """Optional hook: called after the full run finishes."""
