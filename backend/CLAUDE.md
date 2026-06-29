# Backend

FastAPI + SQLAlchemy 2.0 (typed `Mapped` style) + Pydantic v2. Python 3.12 required.
All commands run from `backend/` unless noted.

## Commands

```bash
uv sync                          # install backend + dev deps into .venv/
uv run pytest                    # run the test suite (in-memory SQLite, no DB needed)
uv run pytest tests/test_models.py::test_parent_child_relationship  # single test
uv run python -m mypy app        # type-check (strict mode)
uv run alembic revision --autogenerate -m "msg"   # create a migration from model changes
uv run alembic upgrade head      # apply migrations (needs a live Postgres)
uv run uvicorn app.main:app --reload  # run the API locally on :8000

# Dev data management
uv run provision-tenant --troop-name "Troop 123" --slug troop123 --admin-first A --admin-last B  # sign in first!
uv run promote-platform-admin --email you@example.com   # grant global/platform admin (sign in first)
uv run import-twh <tenant-id> <export.xml>  # import TWH XML into a tenant
uv run anonymize-twh <real.xml> <out.xml>   # scrub PII from a TWH export for use as test fixture
uv run reset-tenant <tenant-id>   # clear imported data, keep Clerk admin — then re-import
uv run reset-db                   # nuclear: drop all tables + re-migrate (prompts for confirmation)
uv run reset-db --yes             # same, no prompt (CI/scripts)
```

## Scripts

All one-off CLI scripts live in `backend/scripts/` and are registered as
`[project.scripts]` entry points in `backend/pyproject.toml`. Always invoke via
`uv run <command-name>` — never `python scripts/foo.py` or `uv run python scripts/foo.py`.

To add a new script:
1. Create `backend/scripts/your_script.py` with a `main()` function.
2. Add an entry to `[project.scripts]` in `pyproject.toml`:
   ```toml
   your-command = "scripts.your_script:main"
   ```
3. `uv sync` to install the entry point.
4. `uv run your-command`.

## Conventions

### Models and schemas

ORM models in `app/models/`, Pydantic schemas in `app/schemas/` (kept separate).
Each resource exposes `*Base` / `*Create` / `*Update` / `*Read` schemas.
`*Read` for tenant-scoped models inherits `TrackedRead`; for platform models it
inherits `PlatformRead`. Both use `from_attributes=True`.

- New tenant-scoped models: subclass `TrackedBase`, then add the class to
  `app/models/__init__.py` so it registers on `Base.metadata` for tests and Alembic
  autogenerate.
- New platform-level models: subclass `PlatformBase` instead (no `tenant_id`).

### Adding a new router

1. Create `app/routers/your_resource.py` with
   `router = APIRouter(prefix="/your-resource", tags=["your-resource"])`.
2. Import and register in `app/main.py`: add to the import block and call
   `app.include_router(your_resource.router)`.

### Adding a new TrackedBase table (RLS required)

Every new `TrackedBase` table migration **must** call `rls.enable_rls_for(op, table_name)`
in its `upgrade()` and `rls.disable_rls_for(op, table_name)` in `downgrade()`. Failing
to do so will be caught by the per-PR Postgres RLS CI job.

```python
# In your migration file:
from app.core import rls

def upgrade() -> None:
    op.create_table("my_table", ...)
    rls.enable_rls_for(op, "my_table")   # enables + forces RLS, creates policy, grants DML

def downgrade() -> None:
    rls.disable_rls_for(op, "my_table")  # drops policy, disables RLS, revokes grants
    op.drop_table("my_table")
```

Also add the new table name to the explicit list in
`alembic/versions/1a2b3c4d5e6f_force_rls_enforcement.py` so it is covered by the
policy-completeness introspection test forever.

### Linting and types

- **Ruff** line-length = 100 (not 88). `alembic/versions/` is excluded from linting.
  Select set: `["E", "F", "I", "UP", "B", "SIM", "S"]`; `S101` (assert) suppressed in tests.
- **mypy** runs in `strict = true` mode via `uv run python -m mypy app`.

## Tests

Tests run against an **in-memory SQLite DB** — no live Postgres needed.
All shared fixtures live in `tests/conftest.py`.

### Available fixtures

| Fixture | Tenant | Authenticated as | Use for |
|---------|--------|-----------------|---------|
| `db_session` | n/a | n/a | Direct DB access; basis for all other fixtures |
| `client` | `TENANT_A` | admin (is_admin role) | Standard fixture for most tests |
| `other_client` | `TENANT_B` | same admin | Cross-tenant isolation tests; shares `db_session` |
| `claim_client` | none | `NEW_USER_ID` (no Member row) | Invite/claim and onboarding flows |
| `platform_admin_client` | none | platform superadmin | SaaS control-plane tests |
| `support_client` | none | platform support role | Verifying superadmin-only boundaries |

Auth is bypassed in tests via `X-Test-User-ID` header (no real JWT needed).
Tenant is set via `X-Tenant-ID` header. Tenant row lookup is also bypassed — tests
can use arbitrary UUIDs (`TENANT_A`, `TENANT_B`) without inserting `Tenant` rows.

Constants available from `conftest`: `TENANT_A`, `TENANT_B`, `ADMIN_USER_ID`,
`NEW_USER_ID`, `PLATFORM_ADMIN_USER_ID`, `PLATFORM_SUPPORT_USER_ID`.

### Writing a new test

```python
def test_my_feature(client: TestClient, db_session: Session) -> None:
    resp = client.post("/my-resource/", json={"name": "foo"})
    assert resp.status_code == 201
    # Use db_session to assert DB state directly when needed
```

Use `client` for standard tenant-scoped tests. Combine `client` + `db_session` when
you need to inspect or set up DB state alongside HTTP calls.

## TroopWebHost XML importer (`app/importers/twh.py`)

`TwhImporter(session, tenant_id).run(root)` imports a parsed TWH full-data XML
export into the target tenant. Supported record types (in import order):

| TWH element | OpenTroop model | Notes |
|---|---|---|
| `Patrol` | `Group` (group_type=patrol) | `Patrol_Name` → `name`; scout patrol → `GroupMember` |
| `Person` | `Member` | `Adult_Flag`, `Alumni_Flag`, `Swim_Level`, `Patrol`, OA fields |
| `Relationship` | `MemberRelationship` | Only `Parent` seen in practice; `guardian`, `sibling` also mapped |
| `Leadership_Position` + `*_Leadership_History` | `Position` + `MemberPositionAssignment` | All terms imported with dates (`End_Date` empty ⇒ current); positions matched by slug → BSA `Position_Code` crosswalk → created |
| `Location` | `Location` | `Disabled_Flag=Y` skipped |
| `Event_Type` | `EventType` | Capability flags translated 1-to-1; `is_system=False` |
| `Event` | `Event` | `linked_event_id` resolved in a second pass |
| `Event_Participant` | `EventParticipant` | `?` flag → `None` for `attended`, `True` for `signed_up` |

TWH datetime format: `M/D/YYYY H:MM:SS AM/PM` (parsed by `_parse_datetime` /
`_parse_date`). These are naive *local* times; `_parse_datetime` interprets them
in the importer's `source_tz` and converts to UTC for storage (`source_tz`
defaults to UTC). TWH integer IDs never persist; every row gets a new UUIDv7.

Invoke via `uv run import-twh <tenant-uuid> path/to/export.xml [--timezone America/New_York]`.
The same `timezone` is accepted as a form field on `POST /import/twh`.
Test fixture: `backend/tests/fixtures/sample_twh_minimal.xml` — all PII is fake.
The real TWH export and any anonymized samples are blocked by `reference/.gitignore`.
