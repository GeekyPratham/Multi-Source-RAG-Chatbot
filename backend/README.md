# InsightAgent AI API — Backend

## Database Migrations with Alembic

This project uses [Alembic](https://alembic.sqlalchemy.org/) as the single source of truth for database schema migrations. All schema changes are maintained through version-controlled migration files rather than manually executing `ALTER TABLE` statements during application startup.

### Why Alembic?

- **Version-controlled schema**: Every schema change is captured in a migration file tracked in Git.
- **Autogeneration**: Alembic can compare SQLAlchemy models against the database and generate migration files automatically.
- **Upgrade/downgrade**: Each migration has both `upgrade()` and `downgrade()` implementations for forward and backward compatibility.
- **Production-safe**: Migrations run as a separate deployment step, not automatically on application startup.
- **Existing data preserved**: Alembic migrations handle schema changes without dropping or recreating tables.

### Alembic Configuration

- **Config file**: `backend/alembic.ini`
- **Environment script**: `backend/alembic/env.py` (async SQLAlchemy support)
- **Migration templates**: `backend/alembic/script.py.mako`
- **Migration files**: `backend/alembic/versions/`
- **Database URL**: Read from the `DATABASE_URL` environment variable (never hardcoded)

The `env.py` reuses the existing async SQLAlchemy engine and `Base` from `app.core.database`. All SQLAlchemy models in `app.core.models_db` are imported so that `Base.metadata` is complete for autogeneration.

### Initial Database Setup

Run commands from `backend/` in PowerShell. Alembic loads `DATABASE_URL` from
the process environment or `backend/.env`; the process environment takes
precedence. Ensure the database itself already exists and is reachable.

```powershell
cd D:\Project\AI\multitool-ai-chatbot\backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic current
```

The checked-in `001_initial_schema` revision creates the schema represented by
the current models. Do not generate another initial migration. For an existing
database whose schema already matches these models, `alembic stamp
001_initial_schema` updates only Alembic's revision tracking; it does not apply
or verify schema changes. Back up important databases before changing revision
tracking.

If Alembic reports `Can't locate revision identified by '<revision>'`, the
database refers to a migration file missing from this checkout. Restore that
exact revision and its parent migrations unless you are intentionally
re-baselining every environment. Re-baselining changes revision tracking only;
first verify the database schema matches the new baseline.

### Adding or Changing a Model Column

1. Edit the SQLAlchemy model in `app/core/models_db.py`.
2. Generate a migration:

   ```powershell
   .\.venv\Scripts\python.exe -m alembic revision --autogenerate -m "add phone number to users"
   ```

3. Review the generated `upgrade()` and `downgrade()` operations in
   `alembic/versions/`. Autogeneration is a draft; it may not detect every
   change, and migrations for non-null columns on populated tables often need
   a default or a staged data migration.
4. Apply the reviewed migration and confirm the database revision:

   ```powershell
   .\.venv\Scripts\python.exe -m alembic upgrade head
   .\.venv\Scripts\python.exe -m alembic current
   ```

Useful commands, also run from `backend/`:

```powershell
.\.venv\Scripts\python.exe -m alembic history
.\.venv\Scripts\python.exe -m alembic heads
.\.venv\Scripts\python.exe -m alembic check
.\.venv\Scripts\python.exe -m alembic downgrade -1
```

Downgrades can lose data when dropping columns or tables; inspect the revision
before rolling back.

### Application Startup

The application startup (`init_db()` in `app/core/database.py`) no longer performs schema creation or migrations. It only verifies database connectivity with a `SELECT 1` query. All schema changes must be applied separately using `alembic upgrade head`.

### Production Deployment

1. Run migrations as a separate deployment step before deploying the application:
   ```powershell
   .\.venv\Scripts\python.exe -m alembic upgrade head
   ```

2. Never run migrations automatically from multiple application instances simultaneously.

3. Always back up the database before running destructive migrations.

4. Do not automatically downgrade if an application deployment fails.

### Files

| File | Purpose |
|------|---------|
| `alembic.ini` | Alembic configuration |
| `alembic/env.py` | Async migration environment |
| `alembic/script.py.mako` | Migration file template |
| `app/core/database.py` | Database engine, session factory, Base, and `init_db()` (connectivity check only) |
| `app/core/models_db.py` | SQLAlchemy ORM models |
