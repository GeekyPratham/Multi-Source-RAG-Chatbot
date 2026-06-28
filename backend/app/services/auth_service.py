"""services/auth_service.py — JWT creation/validation, password hashing, Redis token store."""
from __future__ import annotations
import os
import uuid
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.models_db import User, RefreshToken
from app.core.database import async_session_factory
from app.utils.logger import log

# ── Config from environment ───────────────────────────────────────────────────
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me-in-production-" + uuid.uuid4().hex[:16])
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_EXPIRE_MIN", "15"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_EXPIRE_DAYS", "7"))

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Lazy Redis connection (optional — degrades gracefully)
_redis: Optional[aioredis.Redis] = None
_redis_available: bool = True


async def get_redis() -> Optional[aioredis.Redis]:
    global _redis, _redis_available
    if not _redis_available:
        return None
    if _redis is None:
        try:
            r = aioredis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=2)
            await r.ping()
            _redis = r
            log.info("Connected to Redis at %s", REDIS_URL)
        except Exception as e:
            log.warning("Redis not available at %s — falling back to DB-only token storage (%s)", REDIS_URL, e)
            _redis_available = False
            return None
    return _redis


async def close_redis():
    global _redis
    if _redis:
        try:
            await _redis.close()
        except Exception:
            pass
        _redis = None
        log.info("Redis connection closed")


# ── Password utilities ────────────────────────────────────────────────────────
def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── JWT utilities ─────────────────────────────────────────────────────────────
def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": user_id, "exp": expire, "type": "access"}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token() -> tuple[str, str]:
    """Returns (raw_token, token_hash)."""
    raw = uuid.uuid4().hex + uuid.uuid4().hex  # 64 hex chars
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    return raw, token_hash


def decode_access_token(token: str) -> Optional[str]:
    """Returns user_id if valid, None otherwise."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            return None
        return payload.get("sub")
    except JWTError:
        return None


# ── Redis-backed refresh token operations (best-effort) ───────────────────────
async def store_refresh_token_redis(user_id: str, raw_token: str) -> None:
    r = await get_redis()
    if r is None:
        return  # Redis not available — skip
    key = f"refresh:{user_id}"
    ttl = REFRESH_TOKEN_EXPIRE_DAYS * 86400
    try:
        await r.setex(key, ttl, raw_token)
    except Exception as e:
        log.warning("Redis store failed: %s", e)


async def validate_refresh_token_redis(user_id: str, raw_token: str) -> bool:
    r = await get_redis()
    if r is None:
        return False  # Can't validate without Redis
    try:
        stored = await r.get(f"refresh:{user_id}")
        return stored == raw_token
    except Exception:
        return False


async def delete_refresh_token_redis(user_id: str) -> None:
    r = await get_redis()
    if r is None:
        return
    try:
        await r.delete(f"refresh:{user_id}")
    except Exception:
        pass


# ── Database-backed refresh token persistence (fallback / rotation audit) ─────
async def store_refresh_token_db(user_id: uuid.UUID, token_hash: str, expires_at: datetime) -> None:
    async with async_session_factory() as session:
        rt = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        session.add(rt)
        await session.commit()


async def invalidate_all_refresh_tokens_db(user_id: uuid.UUID) -> None:
    async with async_session_factory() as session:
        result = await session.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == user_id,
                RefreshToken.expires_at > datetime.now(timezone.utc),
            )
        )
        for rt in result.scalars():
            rt.expires_at = datetime.now(timezone.utc)  # expire immediately
        await session.commit()


# ── Full refresh token lifecycle ──────────────────────────────────────────────
async def issue_refresh_token(user_id: uuid.UUID) -> str:
    """Generate, persist, and return the raw refresh token."""
    raw, token_hash = create_refresh_token()
    expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    # Store in Redis for fast lookup
    await store_refresh_token_redis(str(user_id), raw)
    # Store hash in DB for audit
    await store_refresh_token_db(user_id, token_hash, expires_at)

    return raw


async def rotate_refresh_token(old_user_id: str, old_raw_token: str) -> Optional[tuple[str, str, str]]:
    """Validate old token and issue new pair. Returns (access_token, refresh_token, user_id) or None."""
    # Validate the old token
    if not await validate_refresh_token_redis(old_user_id, old_raw_token):
        return None

    user_uuid = uuid.UUID(old_user_id)
    # Delete old
    await delete_refresh_token_redis(old_user_id)
    await invalidate_all_refresh_tokens_db(user_uuid)

    # Issue new
    new_access = create_access_token(old_user_id)
    new_refresh = await issue_refresh_token(user_uuid)
    return new_access, new_refresh, old_user_id


# ── User lookup helper ────────────────────────────────────────────────────────
async def get_user_by_email(email: str, session: AsyncSession) -> Optional[User]:
    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_id(user_id: uuid.UUID, session: AsyncSession) -> Optional[User]:
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()