# Caching Rules — Spending Tracker SaaS

Derived from the 2026-07-29 blueprint audit (E16).

---

## RULE-CACHE-01: Cache keys must include user_id

Any cache entry for analytics, aggregates, or per-user computed data must include `user_id` as a dimension in the cache key tuple. A key without `user_id` is a cross-user data leak for any multi-tenant deployment.

**Correct pattern**:
```python
key = ("analytics_monthly", str(current_user.id), year, month)
```

**Forbidden**:
```python
key = ("analytics_monthly", year, month)          # all users share one entry
key = ("analytics_monthly", "default", year, month)  # placeholder = data leak
```

Review every `cache.set()` call before merging. If `current_user` is not in scope, the cache call is in the wrong place.

---

## RULE-CACHE-02: Invalidate on every write

Cache entries for transaction-derived aggregates must be invalidated on every transaction write (create, patch, reverse, commit, discard). TTL is a safety net, not the primary coherence mechanism.

**Pattern**: call `cache.clear()` (or a targeted key invalidation) at the end of any route that modifies transactions, statements, or categories. Do not rely on TTL expiry alone for financial data.

---

## RULE-CACHE-03: No stampede on cold start (future)

For a small user base (< 100 users), concurrent cache misses hitting the DB simultaneously is acceptable. When traffic grows:

1. Add a per-key asyncio lock to serialize concurrent fetches:
   ```python
   _locks: dict[tuple, asyncio.Lock] = {}
   async def get_or_compute(key, compute_fn):
       lock = _locks.setdefault(key, asyncio.Lock())
       async with lock:
           val = cache.get(key)
           if val is _MISS:
               val = await compute_fn()
               cache.set(key, val)
           return val
   ```
2. This is the singleflight pattern — only the first waiter computes; the rest block until the result is cached.

---

## RULE-CACHE-04: Bounded cache size

The in-process TTL cache is an unbounded dict. Add a max-size eviction when the number of active users × distinct query dimensions exceeds ~500 entries to prevent memory growth.

**Simple LRU-bounded wrapper** (stdlib, no deps):
```python
from functools import lru_cache  # for reference
import collections

_maxsize = 500
_store: dict = {}
_order: collections.OrderedDict = collections.OrderedDict()

def set(key, value, ttl=60):
    if len(_order) >= _maxsize and key not in _order:
        oldest = next(iter(_order))
        _order.pop(oldest)
        _store.pop(oldest, None)
    _store[key] = (value, time.monotonic() + ttl)
    _order[key] = True
    _order.move_to_end(key)
```

---

## RULE-CACHE-05: Single-worker invariant is a hard gate

Before any change that increases `--workers` above 1, the in-process cache (`backend/src/core/cache.py`) must be replaced with a Redis-backed implementation. The interface is designed for this swap:

```python
# Drop-in Redis replacement keeps the same signature:
async def get(key: tuple) -> Any: ...
async def set(key: tuple, value: Any, ttl: int = 60) -> None: ...
async def clear() -> None: ...
```

Increasing workers without swapping the cache causes silent correctness failures (stale analytics) that are hard to detect and debug.
