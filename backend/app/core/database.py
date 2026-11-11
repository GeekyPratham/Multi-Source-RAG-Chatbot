"""core/database.py — async SQLAlchemy engine and session factory."""
from __future__ import annotations
import os
import re
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
# AsyncSession is "Ek single “conversation” with DB"
# create_async_engine -> DB se connection ka source banata hai
# async_sessionmaker -> ek factory function hai jo AsyncSession objects banata hai or Naye sessions banata hai
from sqlalchemy.orm import DeclarativeBase
from app.utils.logger import log


def _ensure_async_url(url: str) -> str:
    """Convert postgresql:// to postgresql+asyncpg:// if needed."""
    if url.startswith("postgresql://") and "+asyncpg" not in url:
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def _sanitize_url(url: str) -> str:
    """Remove non-standard query params that asyncpg doesn't support."""
    blocked_params = {"channel_binding", "sslmode"}
    parts = url.split("?")
    if len(parts) > 1:
        base = parts[0]
        params = parts[1].split("&")
        filtered = [p for p in params if p.split("=")[0] not in blocked_params]
        if filtered:
            return base + "?" + "&".join(filtered)
        return base
    return url


raw_url = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://insightagent:insightagent@localhost:5432/insightagent",
)

DATABASE_URL = _sanitize_url(_ensure_async_url(raw_url))

engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
#echo=True It controls whether SQLAlchemy prints SQL statements to its engine log.
#pool_pre_ping = True checks whether a connection is alive before using it.If the connection is stale, SQLAlchemy can discard it and establish another connection.This helps improve reliability.

async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
#expire_on_commit=False prevents SQLAlchemy from expiring (invalidating) all instances after a commit, allowing you to continue using them without reloading from the database.



#All your database ORM models inherit from this class.
class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    """Dependency that yields a database session."""
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Create all tables and run safe migrations on startup.

    Runs idempotent ALTER statements to:
    - Make llm_provider and llm_model nullable
    - Convert llm_provider from ENUM to VARCHAR(50) if needed
    - Add llm_base_url column if missing
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    migrations = (
        "ALTER TABLE users ALTER COLUMN llm_provider DROP NOT NULL",
        "ALTER TABLE users ALTER COLUMN llm_model DROP NOT NULL",
        "ALTER TABLE users ALTER COLUMN llm_provider TYPE VARCHAR(50)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS llm_base_url VARCHAR(500)",
    )
    async with engine.begin() as conn:
        for stmt in migrations:
            await conn.execute(text(stmt))

    log.info("Database initialized and migrations applied")