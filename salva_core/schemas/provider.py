from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from salva_core.schemas.enums import ProviderFamily, ProviderStatus, RetrievalProviderKind


class ProviderDescriptor(BaseModel):
    kind: RetrievalProviderKind
    name: str
    description: str
    supports_custom_endpoint: bool = True
    supports_site_domains: bool = False
    enabled_by_default: bool = True
    env_vars: list[str] = Field(default_factory=list)


class ProvidersResponse(BaseModel):
    items: list[ProviderDescriptor]
    total: int


class ProviderInterfaceDescriptor(BaseModel):
    family: ProviderFamily
    kind: str
    name: str
    description: str
    status: ProviderStatus = "available"
    supports_custom_endpoint: bool = True
    supports_health_check: bool = True
    supports_local_mode: bool = True
    enabled_by_default: bool = True
    env_vars: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ProviderCatalogResponse(BaseModel):
    items: list[ProviderInterfaceDescriptor]
    total: int


class LLMProviderDescriptor(BaseModel):
    name: str
    kind: Literal["omlx"]
    description: str
    default_model: str | None = None
    supports_custom_endpoint: bool = True
    supports_health_check: bool = True
    env_vars: list[str] = Field(default_factory=list)


class LLMProvidersResponse(BaseModel):
    items: list[LLMProviderDescriptor]
    total: int


class LLMHealthResponse(BaseModel):
    name: str
    available: bool
    base_url: str | None = None
    model_name: str | None = None
    latency_ms: float | None = None
    message: str | None = None
    checked_at: datetime
