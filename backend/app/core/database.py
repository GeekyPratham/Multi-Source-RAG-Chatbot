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

# Why is this important?
# Because your application uses create_async_engine().
# You need an asynchronous-compatible driver.

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

# This function removes specific query parameters from the connection string.
# Example:
# postgresql://user:password@localhost:5432/test?sslmode=require&channel_binding=require

# After sanitization, it becomes:
# postgresql://user:password@localhost:5432/test  
# 
# However, there is an important production consideration here.

# Do not blindly remove SSL settings in production.

# If your database requires TLS, removing sslmode without configuring equivalent TLS options in asyncpg could weaken security or cause a connection failure.

# A better approach is to explicitly configure the SSL context supported by your database driver.  

raw_url = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://insightagent:insightagent@localhost:5432/insightagent",
)

DATABASE_URL = _sanitize_url(_ensure_async_url(raw_url))

engine = create_async_engine(DATABASE_URL, echo=True, pool_pre_ping=True)
#echo=True It controls whether SQLAlchemy prints SQL statements to its engine log.
#pool_pre_ping = True checks whether a connection is alive before using it.If the connection is stale, SQLAlchemy can discard it and establish another connection.This helps improve reliability.

async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
#expire_on_commit=False prevents SQLAlchemy from expiring (invalidating) all instances after a commit, allowing you to continue using them without reloading from the database.



#All your database ORM models inherit from this class.
class Base(DeclarativeBase):
    pass


# Because SQLAlchemy needs a common base that maintains metadata about database tables.

# Think of Base as the central registry of your ORM models.

# It tracks information such as:
# - Table names.
# - Columns.
# - Primary keys.
# - Foreign keys.
# - Relationships.
# - Indexes.
# This information is stored in: Base.metadata



# This function introduces an important FastAPI concept called Dependency Injection.

async def get_db() -> AsyncSession:
    """Dependency that yields a database session."""
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()
# What happens with get_db() or DI?
# 1. The client sends a request.
# 2. FastAPI identifies get_db as a dependency.
# 3. FastAPI executes get_db().
# 4. A database session is created.
# 5. The endpoint receives that session.
# 6. The endpoint executes its query.
# 7. When the request's dependency lifecycle finishes, the session is closed.

# why yield instead of return?
# return returns a value and finishes the function.

# yield temporarily provides a value and allows execution to resume later.

# This lets FastAPI perform setup before the endpoint and cleanup after it finishes.

# This pattern is commonly used for:
# - Database connections.
# - File resources.
# - Temporary resources.
# - Request-scoped services.

async def init_db():
    """Validate database connectivity on application startup.

    Schema creation and migrations are no longer performed here.
    All schema changes are managed exclusively through Alembic migration
    files located in the alembic/versions directory.

    Run migrations separately using:
        alembic upgrade head

    This function only verifies that the database is reachable.
    """
    async with engine.begin() as conn:
        # Simple connectivity check — does not modify schema.
        await conn.execute(text("SELECT 1"))

    log.info("Database connectivity verified")