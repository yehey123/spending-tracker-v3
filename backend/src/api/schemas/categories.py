from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    icon: str | None = None
    parent_id: int | None = None


class CategoryUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    icon: str | None = None
    parent_id: int | None = None


class CategoryOut(BaseModel):
    id: int
    name: str
    color: str | None
    icon: str | None
    slug: str | None = None
    is_system: bool = False
    parent_id: int | None = None
    children: list[CategoryOut] = []
    model_config = ConfigDict(from_attributes=True)


# Must rebuild after forward reference is fully defined
CategoryOut.model_rebuild()
