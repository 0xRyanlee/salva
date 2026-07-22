from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MatePricing(BaseModel):
    provider_name: str | None = None
    model_name: str | None = None
    usd_per_1k_tokens: float | None = None
    pricing_catalog_url: str | None = None
    pricing_catalog_path: str | None = None
    currency: str = "USD"
    tokens_per_candidate: int = 1200
    manual_review_seconds_per_candidate: float = 18.0
    manual_retry_seconds_per_failed_source_attempt: float = 12.0


class MateRequest(BaseModel):
    pricing: MatePricing = Field(default_factory=MatePricing)


class PricingCatalogEntry(BaseModel):
    provider_name: str | None = None
    model_name: str | None = None
    usd_per_1k_tokens: float | None = None
    currency: str = "USD"
    notes: list[str] = Field(default_factory=list)


class PricingCatalogResponse(BaseModel):
    generated_at: datetime | None = None
    source_name: str | None = None
    source_url: str | None = None
    source_latency_ms: float | None = None
    entries: list[PricingCatalogEntry] = Field(default_factory=list)
    resolved_quote: PricingCatalogEntry | None = None
    resolved: bool = False


class MateReport(BaseModel):
    run_id: str
    objective: str
    output_profile: str
    experience_profile: str
    generated_at: datetime
    generation_latency_ms: float = 0.0
    raw_count: int = 0
    qualified_count: int = 0
    source_attempt_count: int = 0
    plugin_report_count: int = 0
    estimated_candidate_units_saved: int = 0
    estimated_time_saved_seconds: float = 0.0
    estimated_llm_calls_saved: float = 0.0
    estimated_tokens_saved: int = 0
    estimated_api_cost_saved: float | None = None
    pricing_applied: bool = False
    pricing_source_name: str | None = None
    pricing_source_url: str | None = None
    pricing_source_latency_ms: float | None = None
    assumptions: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    details: dict[str, Any] = Field(default_factory=dict)
