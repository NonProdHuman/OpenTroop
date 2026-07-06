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
uv run link-admin <tenant-id> --first A --last B  # link your signed-in User to an admin Member (fixes provision-tenant run before first sign-in)
uv run import-twh <tenant-id> <export.xml>  # import TWH XML into a tenant
uv run anonymize-twh <real.xml> <out.xml>   # scrub PII from a TWH export (local use only — never commit)
uv run generate-twh-fixture       # regenerate the committed fully synthetic TWH fixtures
uv run reset-tenant <tenant-id>   # clear imported data, keep Clerk admin — then re-import
uv run reset-db                   # nuclear: drop all tables + re-migrate (prompts for confirmation)
uv run reset-db --yes             # same, no prompt (CI/scripts)

# Advancement (Pillar 4, GH-92)
uv run seed-advancement           # load/refresh the global rank & merit badge catalog
uv run recompute-advancement      # scheduled auto-credit pass (tenure/POR thresholds)

# Hard delete (GH-222, ADR 0010)
uv run reap-tombstones            # physically delete purged-member tombstones past retention (cron)
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

### Dependencies

- **HTTP client is `httpx2`, imported as `import httpx2 as httpx`** (see
  [ADR 0007](../docs/adr/0007-httpx2-http-client.md)). This is deliberate, **not a
  typo or typosquat** — `httpx2` is Pydantic's maintained continuation of `httpx`
  with a drop-in-compatible API. Do not "fix" the import back to `httpx`.

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
| `Event_Participant` | `EventParticipant` | `?` flag → `None` for `attended`, `True` for `signed_up`; camping nights exist **only** as participant overrides in TWH (the `Event` element has no `Camping_Nights` field) |
| `Advancement_Earned` | `MemberRankProgress` | Rank awards only: `completed_date=Date_Earned` (BOR), `awarded_date=Date_Awarded ?? COH_Date`. Eagle Palms + Venturing/Ship awards warned + skipped |
| `Advancement_Requirement_Earned` | `MemberRequirementCompletion` | `approved`, `recorded_via=import`; crosswalk by rank code + requirement number/letter (exact → bare-leaf fallback → container expands to leaf children); deduped per (member, requirement) |
| `Merit_Badge` | `MemberMeritBadge` | Badge matched by name (case-insensitive, ` (YYYY rqmts)` suffix stripped) against the **global** catalog; unknown names warned + skipped — a tenant import never writes the platform catalog. Null `Date_Earned` ⇒ partial in progress |
| `Requirement_Pending` | `MemberRequirementCompletion` | `Pending`→`reported`, `Rejected`→`rejected`; `Approved` skipped (already landed as earned); MB-scoped rows skipped |
| `BSA_Award`, `BSA_Requirement` | *(crosswalk only)* | The export's own award/requirement catalog — read to resolve ids, never stored. Requirement descriptions in real exports are numeric text-blob refs, so **numbering is the only usable identity** |

**Advancement precondition:** the global catalog must be seeded (`uv run seed-advancement`)
before import — with no `Rank` rows, all advancement records are skipped behind one warning.
Deployed environments seed automatically: the image CMD runs `seed-advancement` (with the
migrate credentials) right after `alembic upgrade head`, and the API logs a startup WARNING
if the catalog is still empty (GH-241). Run `uv run recompute-advancement` after import to
pick up auto-credit thresholds.

**All other record types are deliberately skipped** (GH-205 sweep of a full 68-type export;
field inventory in [`data/twh/export_schema.json`](data/twh/export_schema.json)):

| Skipped types | Reason |
|---|---|
| `Adult_Training`, `Scout_Training`, `Training_Course`, `BSA_Adult_Training` | No training model yet — blocked on #122 (YPT); revisit there |
| `Award`, `Award_Type` (service stars, square knots), `Other_Activity` (non-event activity credits) | No OpenTroop model yet — follow-up tracked in the GH-205 close-out; `Other_Activity` matters because TWH credits service hours/camping nights outside events, which OT computes from events only |
| `Merit_Badge_Requirement_Earned` | Per-MB-requirement tracking deliberately deferred (GH-92 — the counselor owns it) |
| `Dynamic_Group`, `Dynamic_Group_Leadership`, `Dynamic_Group_Patrol` | TWH's rule-based groups ≈ OT `Group`+`GroupRule`, but rule semantics differ; import deferred |
| `Event_Shift`, `Event_Shift_Participant`, `Event_Shift_Participant_Delete_Audit` | No shift model |
| `Email`, `Email_Group`, `Email_Group_Member`, `Email_Recipient`, `Email_Recipient_Log`, `Announcement`, `Announcement_Person_Opened`, `Newsletter_Section_Order` | Historical comms logs; OT has its own messaging layer (GH-86) |
| `Delete_Audit`, `Event_Participant_Audit`, `Monetary_Transaction_Audit` | TWH audit shadows; OT keeps its own timestamps (`Delete_Audit` may inform dual-run sync later — see twh-sync spec) |
| `Budget_Item`, `Budget_Value`, `Fiscal_Year`, `Monetary_*`, `Merchandise_*`, `Subaccount_Type`, `BSA_Transaction_Type`, `Inventory_*` | Finance/inventory is a future pillar |
| `Recharter_Year`, `Recharter_Year_Member` | Recharter tracking not built |
| `Event_Photo` | References TWH-hosted binaries not present in the export |
| `Custom_Form`, `Custom_Form_Section`, `Troop_Form`, `Local_Text`, `Dress_Code`, `Shirt_Size`, `Person_Category`, `Person_Leadership_Mass_Update`, `BSA_Rank_Name`, `BSA_Award_Selection_Type` | TWH UI/config reference data; OT equivalents are seeded or N/A |
| `Troop_Information` | The tenant already exists with its own name/slug |

TWH datetime format: `M/D/YYYY H:MM:SS AM/PM` (parsed by `_parse_datetime` /
`_parse_date`). These are naive *local* times; `_parse_datetime` interprets them
in the importer's `source_tz` and converts to UTC for storage (`source_tz`
defaults to UTC). TWH integer IDs never persist; every row gets a new UUIDv7.

Every imported row carries **source provenance** (`SourceTracked` mixin: `source_system="twh"`,
`source_id` = the TWH `<i>`, `source_updated_at` = `Last_Update_UTC`) so a future incremental
sync can match-and-upsert instead of duplicating. This is groundwork only — no sync engine
reads it yet. See [`docs/spec/twh-sync.md`](../docs/spec/twh-sync.md).

Invoke via `uv run import-twh <tenant-uuid> path/to/export.xml [--timezone America/New_York]`.
The same `timezone` is accepted as a form field on `POST /import/twh`.

Test fixtures: `backend/tests/fixtures/sample_twh_minimal.xml` (hand-written minimal roster)
and `synthetic_troop1.xml.gz` / `synthetic_troop2.xml.gz` — **fully synthetic** full exports
covering all 68 record types, regenerated byte-identically by `uv run generate-twh-fixture`
(a drift test enforces this; gzipped to stay under the repo's 500 KB file cap — use
`uv run generate-twh-fixture --troop 1 --out /tmp/t1.xml` or `gunzip -c` to eyeball the XML).
Real TWH exports and anonymized samples must never be committed — they are blocked by
`reference/.gitignore`; `uv run anonymize-twh` output is for local use only.
