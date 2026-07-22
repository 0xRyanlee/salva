from __future__ import annotations

from pydantic import BaseModel, Field

from salva_core.schemas.enums import OutputProfile


class OutputTransformFieldSpec(BaseModel):
    name: str
    source: str | None = None
    description: str
    required: bool = False
    examples: list[str] = Field(default_factory=list)


class OutputTransformProfileSpec(BaseModel):
    profile: OutputProfile
    description: str
    caller_types: list[str] = Field(default_factory=list)
    fields: list[OutputTransformFieldSpec] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class OutputTransformCatalog(BaseModel):
    items: list[OutputTransformProfileSpec] = Field(default_factory=list)
    total: int = 0
