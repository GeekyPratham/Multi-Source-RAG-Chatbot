"""services/redis_service.py — Unified Redis client supporting Upstash REST + local Redis.

Uses Upstash Redis REST API when UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN
are set (preferred for production). Falls back to local redis.asyncio otherwise.
"""
from __future__ import annotations
import os
import time
from typing import Optional, Callable, Awaitable
from app.utils.logger import log

# ── Config from environment ───────────────────────────────────────────────────
UPSTASH_REST_URL = os.getenv("UPSTASH_REDIS_REST_URL", "").strip()
UPSTASH_REST_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN", "").strip()
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# ── Upstash REST client (lazy) ────────────────────────────────────────────────
_upstash_client: Optional[object] = None  # Will hold the Upstash Redis client

# ── Local redis.asyncio client (lazy) ─────────────────────────────────────────
_local_redis: Optional["aioredis.Redis"] = None  # noqa: F821

# ── State ─────────────────────────────────────────────────────────────────────
_client_type: Optional[str] = None  # "upstash" or "local" or None
_upstash_available: bool = False
_local_available: bool = False


def _get_upstash_client():
    """Lazily import & return the Upstash Redis client."""
    global _upstash_client
    if _upstash_client is not None:
        return _upstash_client
    try:
        from upstash_redis import Redis as UpstashRedis
        _upstash_client = UpstashRedis(
            url=UPSTASH_REST_URL,
            token=UPSTASH_REST_TOKEN,
        )
        log.info("Upstash Redis client created (REST)")
        return _upstash_client
    except ImportError:
        log.warning("upstash-redis package not installed")
        return None
    except Exception as e:
        log.warning("Failed to create Upstash Redis client: %s", e)
        return None


async def _get_local_redis():
    """Lazily create & return a local redis.asyncio client."""
    global _local_redis
    if _local_redis is not None:
        return _local_redis
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=2)
        await r.ping()
        _local_redis = r
        log.info("Local Redis connected at %s", REDIS_URL)
        return _local_redis
    except Exception as e:
        log.warning("Local Redis not available at %s: %s", REDIS_URL, e)
        return None


# ── Public API ────────────────────────────────────────────────────────────────

async def init_redis() -> bool:
    """Initialize Redis (Upstash preferred, local fallback) and verify connectivity.

    Returns True if Redis is usable, False otherwise.
    Logs detailed status so you can verify it's working.
    """
    global _client_type, _upstash_available, _local_available

    # Try Upstash first
    if UPSTASH_REST_URL and UPSTASH_REST_TOKEN:
        client = _get_upstash_client()
        if client is not None:
            try:
                # Ping via Upstash REST by setting and getting a test key
                test_key = f"__init_test_{int(time.time())}"
                client.set(test_key, "ok")
                result = client.get(test_key)
                client.delete(test_key)
                if result == "ok":
                    _upstash_available = True
                    _client_type = "upstash"
                    log.info(
                        "=" * 60
                        + "\n[OK] Upstash Redis CONNECTED successfully!"
                        + "\n   URL: %s"
                        + "\n" + "=" * 60,
                        UPSTASH_REST_URL.split("@")[0] if "@" in UPSTASH_REST_URL else UPSTASH_REST_URL,
                    )
                    return True
                else:
                    log.warning("Upstash ping returned unexpected value: %s", result)
            except Exception as e:
                log.warning("Upstash Redis ping failed: %s — trying local fallback", e)
        else:
            log.warning("Could not create Upstash client — trying local fallback")
    else:
        log.info("No Upstash credentials found — trying local Redis")

    # Fallback to local Redis
    r = await _get_local_redis()
    if r is not None:
        _local_available = True
        _client_type = "local"
        log.info(
            "=" * 60
            + "\n[OK] Local Redis CONNECTED at %s"
            + "\n" + "=" * 60,
            REDIS_URL,
        )
        return True

    _client_type = None
    log.warning(
        "=" * 60
        + "\n[FAIL] Redis is NOT available."
        + "\n   Refresh token rotation and rate limiting will be degraded."
        + "\n   To fix: configure UPSTASH_REDIS_REST_URL/TOKEN in .env"
        + "\n   Or: start a local Redis server on %s"
        + "\n" + "=" * 60,
        REDIS_URL,
    )
    return False


async def close_redis():
    """Close the Redis connection gracefully."""
    global _local_redis, _upstash_client
    if _local_redis:
        try:
            await _local_redis.close()
        except Exception:
            pass
        _local_redis = None
    _upstash_client = None
    log.info("Redis connection(s) closed")


async def setex(key: str, ttl_seconds: int, value: str) -> bool:
    """Set a key with TTL (seconds). Returns True on success."""
    if _client_type == "upstash" and _upstash_client:
        try:
            _upstash_client.setex(key, ttl_seconds, value)
            return True
        except Exception as e:
            log.warning("Upstash setex failed: %s", e)
            return False
    elif _client_type == "local":
        r = await _get_local_redis()
        if r:
            try:
                await r.setex(key, ttl_seconds, value)
                return True
            except Exception as e:
                log.warning("Local Redis setex failed: %s", e)
                return False
    return False


async def get(key: str) -> Optional[str]:
    """Get a value by key. Returns None if missing or on error."""
    if _client_type == "upstash" and _upstash_client:
        try:
            result = _upstash_client.get(key)
            return result
        except Exception as e:
            log.warning("Upstash get failed: %s", e)
            return None
    elif _client_type == "local":
        r = await _get_local_redis()
        if r:
            try:
                result = await r.get(key)
                return result
            except Exception as e:
                log.warning("Local Redis get failed: %s", e)
                return None
    return None


async def delete(key: str) -> bool:
    """Delete a key. Returns True if deleted, False otherwise."""
    if _client_type == "upstash" and _upstash_client:
        try:
            _upstash_client.delete(key)
            return True
        except Exception as e:
            log.warning("Upstash delete failed: %s", e)
            return False
    elif _client_type == "local":
        r = await _get_local_redis()
        if r:
            try:
                await r.delete(key)
                return True
            except Exception as e:
                log.warning("Local Redis delete failed: %s", e)
                return False
    return False


async def incr(key: str) -> Optional[int]:
    """Increment a counter. Returns new value or None on error."""
    if _client_type == "upstash" and _upstash_client:
        try:
            return _upstash_client.incr(key)
        except Exception as e:
            log.warning("Upstash incr failed: %s", e)
            return None
    elif _client_type == "local":
        r = await _get_local_redis()
        if r:
            try:
                return await r.incr(key)
            except Exception as e:
                log.warning("Local Redis incr failed: %s", e)
                return None
    return None


async def expire(key: str, ttl_seconds: int) -> bool:
    """Set TTL on an existing key. Returns True on success."""
    if _client_type == "upstash" and _upstash_client:
        try:
            return _upstash_client.expire(key, ttl_seconds)
        except Exception as e:
            log.warning("Upstash expire failed: %s", e)
            return False
    elif _client_type == "local":
        r = await _get_local_redis()
        if r:
            try:
                return await r.expire(key, ttl_seconds)
            except Exception as e:
                log.warning("Local Redis expire failed: %s", e)
                return False
    return False


def is_available() -> bool:
    """Check if Redis is currently available."""
    return _upstash_available or _local_available


def get_client_type() -> str:
    """Return 'upstash', 'local', or 'none'."""
    return _client_type or "none"