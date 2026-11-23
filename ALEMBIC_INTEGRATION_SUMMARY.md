# Alembic Integration Summary

**Project:** InsightAgent AI Chatbot  
**Backend:** FastAPI + SQLAlchemy 2.0 (async) + PostgreSQL  
**Date:** 2026-11-23  
**Status:** Implementation Complete

---

## Files Created

| File | Purpose |
|------|---------|
| `backend/alembic.ini` | Alembic config — reads DATABASE_URL from env |
| `backend/alembic/env.py` | Async env — reuses existing engine & Base |
| `backend/alembic/script.py.mako` | Migration template |
| `backend/alembic/versions/__init__.py` | Package marker |
| `backend/alembic/versions/001_initial_schema.py` | Initial table creation |
| `backend/alembic/versions/002_legacy_user_llm_columns.py` | Legacy ALTER TABLE conversions |
| `backend/README.md` | Updated with Alembic docs |

## Files Modified

| File | Change |
|------|--------|
| `backend/app/core/database.py` | Removed create_all() and ALTER statements from init_db() → SELECT 1 connectivity check only |
| `backend/README.md` | Added Alembic documentation section |

## Key Design Decisions

- **No second engine** — env.py imports existing engine and Base from app.core.database
- **Async support** — env.py uses asyncio + async_engine_from_config
- **Environment-based config** — DATABASE_URL from env, never hardcoded
- **No auto-migration on startup** — init_db() only verifies connectivity with SELECT 1
- **Defensive migrations** — 002 uses postgresql_using for safe ENUM→VARCHAR casting

## Migration Files

### 001_initial_schema.py
Creates all 5 tables (users, documents, chunks, audit_logs, refresh_tokens) with proper indexes, foreign keys, unique constraints, and JSONB columns.

### 002_legacy_user_llm_columns.py
Converts 4 manual ALTER statements:
1. llm_provider DROP NOT NULL → nullable=True
2. llm_model DROP NOT NULL → nullable=True
3. llm_provider ENUM → VARCHAR(50) via ::varchar(50) cast
4. Add llm_base_url VARCHAR(500) column

Each has upgrade() and downgrade() with data-loss warnings.

## Manual Steps Required

Since the remote database was unreachable from this environment, you must:

1. Verify your database is reachable from the deployment environment
2. Check if existing schema matches 001_initial_schema.py
3. If tables exist and match: run `alembic stamp head`
4. If tables need creation: run `alembic upgrade head`
5. Test CRUD operations after migration
6. Add ALEMBIC_INTEGRATION_SUMMARY.md to .gitignore

## Git Ignore

Add to `.gitignore`:
```
ALEMBIC_INTEGRATION_SUMMARY.md
```

Migration files (backend/alembic/versions/*.py) should be committed to Git — they are version-controlled schema history.

## Commands Summary

All from `backend/` directory:
- `export DATABASE_URL="postgresql+asyncpg://user:password@host:5432/dbname"`
- `alembic revision --autogenerate -m "description"`
- `alembic upgrade head`
- `alembic current`
- `alembic downgrade -1`
- `alembic stamp head` (if schema already matches)

## Production Deployment

1. Backup database
2. Run `alembic upgrade head` as separate deployment step
3. Deploy application code after migrations succeed
4. Never auto-downgrade on deployment failure
5. Use env vars for DATABASE_URL — never commit credentials