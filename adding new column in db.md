Here’s the full workflow for adding `mobile_no` to the `users` table. Your current migration head is `001_initial_schema`, and the database is stamped at that revision. **Create a new migration for this change—don’t edit the initial migration.**

### 1. Confirm you’re targeting the right database

In PowerShell, run commands from `backend/`. Your Alembic setup reads `DATABASE_URL` from the process environment or `backend/.env`; make sure it points to the intended database.

```powershell
cd D:\Project\AI\multitool-ai-chatbot\backend

# Only if your virtual environment is not already active
.\.venv\Scripts\Activate.ps1

alembic current
alembic heads
```

Both commands should show `001_initial_schema`. They confirm Alembic can connect and identify the migration state; they do not change the schema.

### 2. Add the column to the SQLAlchemy model

In `models_db.py`, uncomment or add this field inside `User`, for example after `display_name`:

```python
mobile_no: Mapped[str | None] = mapped_column(
    String(15),
    nullable=True,
)
```

`String(15)` sets the database column type and maximum length. `nullable=True` allows existing users to have no mobile number, so adding the column won’t require filling in values for every existing row.

### 3. Generate a migration

```powershell
alembic revision --autogenerate -m "add mobile no to users"
```

This compares the model metadata with the connected database and creates a new file under `alembic/versions/`. **It does not apply the change to the database.**

### 4. Review the generated migration

Open the new file and confirm it adds only `mobile_no` to `users`. It should be similar to:

```python
def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("mobile_no", sa.String(length=15), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "mobile_no")
```

Check that `down_revision` points to the current head, `001_initial_schema`. If the migration proposes dropping or changing unrelated tables or columns, **don’t apply it**—investigate the model imports and database URL first.

### 5. Apply and verify

```powershell
alembic upgrade head
alembic current
alembic check
```

`upgrade head` applies the migration. `current` should then show the new revision ID, and `check` should report no new upgrade operations.

Commit the model change and migration file together so other environments can apply the same change. Be aware that `alembic downgrade -1` would remove the column and any mobile numbers stored in it. If this field should be exposed through the API, you’ll also need to update the relevant request/response schemas and endpoint logic; adding the database column alone doesn’t do that.



------- for reverting

Yes. Since you confirmed the migration was applied and the column can be dropped, run this from backend/ before deleting or changing any files:


That runs the migration’s downgrade() and removes users.mobile_no and any values stored in it. Keep 170c1c2ee660_add_mobile_no_to_users.py in place until the command succeeds; Alembic needs it to downgrade.

Then comment out or remove the mobile_no field in models_db.py, and delete that migration file. Verify the final state:


Both current and heads should show 001_initial_schema, and check should report no new operations. I haven’t executed the downgrade or file cleanup in this turn.

