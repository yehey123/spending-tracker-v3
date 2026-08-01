"""Upstash Redis client — async, lazy-initialised, None when UPSTASH_REDIS_URL is not set.

Uses redis.asyncio so all Redis I/O is non-blocking and safe from FastAPI's async loop.
"""
from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)

_client = None


async def get_redis():
    """Return a connected async Redis client, or None if Upstash is not configured."""
    global _client
    if _client is not None:
        return _client
    from src.core.config import settings
    if not settings.upstash_redis_url:
        return None
    try:
        import redis.asyncio as aioredis
        _client = aioredis.from_url(settings.upstash_redis_url, decode_responses=True)
        await _client.ping()
        logger.info("Upstash Redis connected")
    except Exception as exc:
        logger.warning("Upstash Redis unavailable — OCR queue disabled: %s", exc)
        _client = None
    return _client


OCR_QUEUE_KEY = "ocr_queue"


async def enqueue_ocr_job(statement_id: int, user_id: str) -> bool:
    """Push a job onto the OCR queue. Returns False if Redis is unavailable."""
    r = await get_redis()
    if r is None:
        return False
    payload = json.dumps({"statement_id": statement_id, "user_id": user_id})
    await r.lpush(OCR_QUEUE_KEY, payload)
    return True


async def dequeue_ocr_job(timeout: int = 5) -> dict | None:
    """Async pop from the OCR queue. Returns None on timeout or when Redis is unavailable."""
    r = await get_redis()
    if r is None:
        return None
    result = await r.brpop(OCR_QUEUE_KEY, timeout=timeout)
    if result is None:
        return None
    _, payload = result
    return json.loads(payload)
