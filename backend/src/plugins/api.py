"""Contract between core and provider plugins. Plugins never import core modules.

A plugin exposes entry points in two groups:
    spending_tracker.ocr_providers  -> a ProviderDescriptor (instance, or class with no-arg init)
    spending_tracker.categorizers   -> a categorizer object (see CategorizerLike)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Protocol, Sequence, runtime_checkable

API_VERSION = 1


@dataclass
class ProviderContext:
    """Core services handed to plugins so they need no core imports."""

    decrypt_secret: Callable[[str | None], str | None] = lambda v: v
    ollama_base_url: str | None = None
    max_output_tokens: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class OCRProviderLike(Protocol):
    supports_categories: bool

    async def extract_text(self, image: Any) -> str: ...

    async def extract_with_categories(self, image: Any, categories: list[dict]) -> str: ...


@runtime_checkable
class ProviderDescriptor(Protocol):
    """Required members. Optional: `max_side: int | None` (image resize cap),
    `list_models(settings, ctx) -> awaitable[list[dict]]` (model sync)."""

    key: str
    label: str
    api_version: int
    config_fields: Sequence[Any]
    credit_weight: int

    def build(self, settings: Any, ctx: ProviderContext) -> OCRProviderLike: ...

    def has_credentials(self, settings: Any) -> bool: ...


@runtime_checkable
class CategorizerLike(Protocol):
    """`classify(prompt, settings, ctx)` returns the raw model text (sync or awaitable)."""

    key: str
    api_version: int

    def has_credentials(self, settings: Any) -> bool: ...

    def classify(self, prompt: str, settings: Any, ctx: ProviderContext) -> Any: ...
