"""Lightweight in-process TTL cache for analytics aggregates.

Only safe with a single uvicorn worker — see Dockerfile CMD.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

_MISS = object()
_store: dict[tuple, tuple[Any, float]] = {}
_MAX_ENTRIES = 2000


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
    if len(_store) >= _MAX_ENTRIES:
        # Evict the soonest-expiring entry to stay bounded.
        oldest = min(_store, key=lambda k: _store[k][1])
        del _store[oldest]
    _store[key] = (value, time.monotonic() + ttl)


def clear_for_user(user_id: uuid.UUID) -> None:
    """Evict all cache entries belonging to the given user."""
    keys = [k for k in _store if k[0] == user_id]
    for k in keys:
        del _store[k]


MISS = _MISS
