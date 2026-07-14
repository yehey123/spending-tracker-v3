from pydantic import BaseModel, ConfigDict, Field


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    color: str = Field(pattern=r'^#[0-9A-Fa-f]{6}$')


class CategoryUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    color: str = Field(pattern=r'^#[0-9A-Fa-f]{6}$')
    icon: str | None = None


class CategoryOut(BaseModel):
    id: int
    name: str
    color: str
    icon: str | None
    model_config = ConfigDict(from_attributes=True)
