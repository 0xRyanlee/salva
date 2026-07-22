from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from salva_core.schemas.enums import EnrichmentPluginName


class PluginReportRecord(BaseModel):
    plugin: EnrichmentPluginName
    target_entity_id: str
    status: str
    applied: bool = False
    message: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class PluginReportsResponse(BaseModel):
    items: list[PluginReportRecord]
    total: int


class PluginDescriptor(BaseModel):
    name: EnrichmentPluginName
    available: bool
    default_auto_enabled: bool
    execution_mode: str
    supported_entity_types: list[str] = Field(default_factory=list)
    notes: str | None = None


class PluginsResponse(BaseModel):
    items: list[PluginDescriptor]
    total: int
