"""Lightweight in-process TTL cache for analytics aggregates.

Only safe with a single uvicorn worker — see Dockerfile CMD.
"""

from __future__ import annotations

import time
from typing import Any

_MISS = object()
_store: dict[tuple, tuple[Any, float]] = {}


def get(key: tuple) -> Any:
    """Return cached value or _MISS if absent/expired."""
    entry = _store.get(key)
    if entry is None:
        return _MISS
    value, expires_at = entry
    if time.monotonic() > expires_at:
        del _store[key]
        return _MISS
    return value


def set(key: tuple, value: Any, ttl: int = 60) -> None:
    _store[key] = (value, time.monotonic() + ttl)


def clear() -> None:
    _store.clear()


MISS = _MISS
