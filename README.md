# OpenTroop

A modern, mobile-first, open-source troop management platform.

OpenTroop is designed to support the complex operational needs of scouting units. Our early focus is providing robust **Event Management** and **Communication** tools, with Advancement and Reporting planned for future phases. Built **offline-first**, it ensures that leaders can continue working seamlessly at camps or in the wilderness without cellular service. Every data record is designed for background synchronization (using client-generatable UUIDv7 keys, per-row timestamps, and soft-delete tombstones) and is securely partitioned by `tenant_id` to support robust multi-tenant SaaS deployments.

**Phase 1 scope:** Membership / Contact Management and Event Management.

## Architecture

```mermaid
graph TD
    subgraph Clients
        WEB["Web App<br/><small>Next.js 16 · Tailwind 4 · shadcn/ui</small>"]
        MOBILE["Mobile Apps<br/><small>iOS (Swift) · Android (Kotlin)</small>"]
        CALAPP["Calendar Apps<br/><small>Apple / Google Calendar</small>"]
    end

    OIDC["OIDC Provider<br/><small>Clerk · Authentik · any IdP</small>"]

    subgraph "FastAPI Backend"
        direction TB
        GW["JWT Validation &amp; Tenant Resolution<br/><small>subdomain / X-Tenant-ID → binds the request to one tenant</small>"]

        R_CAL["Calendar iCal Feed<br/><small>GET /calendar/{token}.ics · unauthenticated<br/>per-member token is the credential — no JWT</small>"]

        subgraph "Routers (REST API)"
            R_MEMBERS["Members &<br/>Relationships"]
            R_GROUPS["Groups &<br/>Audiences"]
            R_EVENTS["Events, RSVP<br/>& Audiences"]
            R_ROLES["Roles &<br/>Permissions"]
            R_SETTINGS["Tenant<br/>Settings"]
            R_IMPORT["Data Import<br/>(TWH XML)"]
            R_AUTH["Auth &<br/>Invite/Claim"]
            R_PLATFORM["Platform<br/>Control Plane"]
        end

        subgraph "Core Services"
            RBAC["RBAC &<br/>Permission Resolver"]
            VIS["Event Visibility<br/>& Audience Filter"]
            PROV["Tenant Provisioning<br/>& Invite Tokens"]
            ICAL["iCal Feed<br/>Generator"]
        end

        subgraph "Tenant Scoping"
            SCOPE["Automatic ORM tenant filter + write stamp<br/><small>every TrackedBase query, no per-route predicate<br/>SET LOCAL app.current_tenant</small>"]
            BYPASS["unscoped() escape hatch<br/><small>cross-tenant identity &amp; platform work</small>"]
        end
    end

    subgraph Data
        direction TB
        RLS["Row-Level Security<br/><small>tenant_isolation policy · fail-closed<br/>opentroop_app enforced · opentroop_admin BYPASSRLS</small>"]
        PG[("PostgreSQL<br/><small>Alembic migrations</small>")]
    end

    SQLITE[("SQLite<br/><small>offline cache</small>")]

    WEB -- "HTTPS / JWT" --> GW
    MOBILE -- "HTTPS / JWT" --> GW
    WEB -. "OIDC login" .-> OIDC
    MOBILE -. "OIDC login" .-> OIDC
    GW -- "JWKS" --> OIDC

    CALAPP -. "webcal:// feed<br/>token is the credential (bypasses JWT)" .-> R_CAL

    GW --> R_MEMBERS & R_GROUPS & R_EVENTS & R_ROLES & R_SETTINGS & R_IMPORT & R_AUTH & R_PLATFORM

    R_MEMBERS & R_GROUPS & R_EVENTS & R_ROLES --> RBAC
    R_EVENTS --> VIS
    R_CAL --> VIS
    R_CAL --> ICAL
    R_PLATFORM --> PROV

    R_MEMBERS & R_GROUPS & R_EVENTS & R_ROLES & R_SETTINGS & R_IMPORT --> SCOPE
    RBAC & VIS & ICAL --> SCOPE
    R_AUTH & R_PLATFORM & PROV --> BYPASS

    SCOPE -- "opentroop_app<br/>(RLS enforced)" --> RLS
    BYPASS -- "opentroop_admin<br/>(BYPASSRLS)" --> RLS
    RLS --> PG

    MOBILE -- "background sync<br/>(planned)" <--> SQLITE

    classDef client fill:#4f8cf7,stroke:#2563eb,color:#fff
    classDef oidc fill:#f59e0b,stroke:#d97706,color:#fff
    classDef gw fill:#6366f1,stroke:#4f46e5,color:#fff
    classDef router fill:#10b981,stroke:#059669,color:#fff
    classDef core fill:#8b5cf6,stroke:#7c3aed,color:#fff
    classDef scope fill:#0ea5e9,stroke:#0284c7,color:#fff
    classDef db fill:#ef4444,stroke:#dc2626,color:#fff
    classDef offline fill:#94a3b8,stroke:#64748b,color:#fff

    class WEB,MOBILE,CALAPP client
    class OIDC oidc
    class GW gw
    class R_AUTH,R_MEMBERS,R_GROUPS,R_EVENTS,R_ROLES,R_SETTINGS,R_PLATFORM,R_IMPORT,R_CAL router
    class RBAC,VIS,PROV,ICAL core
    class SCOPE,BYPASS scope
    class RLS,PG db
    class SQLITE offline
```

**Tenant isolation is defense-in-depth.** Tenant resolution binds each request to a single tenant; the app layer then auto-scopes every `TrackedBase` query (read filter + write stamp) so no route hand-carries a `tenant_id` predicate, and Postgres Row-Level Security re-enforces the same boundary at the database — fail-closed, so a request that forgets to set the tenant sees zero rows rather than all of them. Cross-tenant identity and platform work opts out explicitly through the greppable `unscoped()` escape hatch, paired with the `BYPASSRLS` `opentroop_admin` role.

```
apps/web/      Next.js 16 · Tailwind 4 · shadcn/ui · Clerk auth. Uses middleware for logical domain routing (landing vs admin vs tenant)
apps/mobile/   Expo (React Native) — stub, to be scaffolded
backend/       FastAPI app, ORM models, Pydantic schemas, Alembic, tests
packages/      Shared TypeScript packages (api-client)
```

## Quick start

```bash
./start.sh
```

Validates that your Clerk configuration is consistent between frontend and backend, starts Postgres via Docker, runs the backend with uvicorn, and launches the Next.js dev server. See [docs/local-setup.md](docs/local-setup.md) for the full first-time setup walkthrough.

## Local development

**Frontend** — requires [pnpm](https://pnpm.io) and Node 22.13+ (pnpm 11 needs it):

```bash
npm install -g pnpm
pnpm install                                         # install all workspace deps
cp apps/web/.env.local.example apps/web/.env.local   # add Clerk keys
pnpm dev                                             # start web app on :3000
```

**Backend** — requires [uv](https://docs.astral.sh/uv/) and Python 3.12:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh      # install uv once
```

Then from `backend/`:

```bash
uv sync                                              # create .venv/ and install all deps
uv run pytest                                        # run the test suite (no database needed)
uv run uvicorn app.main:app --reload                 # start the API on :8000
```

### Pre-commit hooks

```bash
# Install pre-commit once (uses uv's global tool layer)
uv tool install pre-commit --with pre-commit-uv

# Wire hooks into git (once per clone)
pre-commit install

# Or run manually
pre-commit run --all-files
```

Hooks cover trailing whitespace, YAML/TOML/JSON validation, secret scanning (gitleaks), Python linting/formatting + types (ruff, mypy — pinned via `uv.lock`), and frontend type-checking + linting (`tsc`, `eslint` — pinned via `pnpm-lock.yaml`).

## Data model (Phase 1)

**Platform-level (global, no tenant scope):**
- **Tenant** — one row per troop; its `id` is the `tenant_id` on every other table.
- **User** — a platform login identity (spans tenants; one person can be a member in multiple troops).
- **Identity** — one OIDC provider credential per User (Google, Apple, passkeys, etc.).

**Tenant-scoped (every row carries `tenant_id`):**
- **Group** — a resolvable set of members (manual and/or dynamic role-based); patrols are groups too. Drives event visibility and messaging.
- **Member** — scouts and adults, with BSA `swim_classification`, group memberships, OA fields, and a nullable link to a `User` login account.
- **MemberRelationship** — guardian/parent/sibling graph linking members.
- **RBAC (two levels)** — `member → Position(s) → FunctionalRole(s) → Permission(s)`.
  A **Position** is what a member *is* (the sole assignable unit); a **FunctionalRole**
  is a named permission bundle; **PositionFunctionalRole** maps positions into roles and
  **FunctionalRolePermission** grants permissions to roles.
- **MemberPositionAssignment** — a member's dated *term* holding a position (the routine write), with a soft-delete audit trail.
- **Location** — reusable named locations (address, phone, directions) referenced by events.
- **EventType** — tenant-customizable event categories with capability flags (`tracks_camping_nights`, `allow_signups`, etc.); six defaults seeded on provisioning.
- **Event** — core event record with dates, location, costs, activity metrics, signup window, and capacity limits.
- **EventOrganizer** — which members are running a given event.
- **EventParticipant** — per-member RSVP, attendance, activity overrides, and permission slip tracking.

All tables inherit `id` (UUIDv7), `created_at`, `updated_at`, and `is_deleted` from a shared base. Tenant-scoped tables additionally carry `tenant_id`.

## Authentication

OpenTroop validates standard OIDC JWTs — any compliant provider works.
See **[docs/auth-provider-setup.md](docs/auth-provider-setup.md)** for step-by-step Clerk (SaaS) and Authentik (self-hosted) setup.

## Deployment

See **[docs/deployment.md](docs/deployment.md)** for a full guide.
The recommended production setup is **Google Cloud Run + Cloud SQL**, which starts at ~$10–15/month and scales to hundreds of troops without rearchitecting.

## Contributing

OpenTroop is developed in the open (AGPLv3) and welcomes contributors.

- **[ROADMAP.md](ROADMAP.md)** — the strategic map: six capability pillars and their order.
- **[GitHub Issues](../../issues)** — the actionable backlog, grouped by [Milestone](../../milestones) (one per pillar). Good starting points are the [`good first issue`](../../issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) and [`help wanted`](../../issues?q=is%3Aissue+is%3Aopen+label%3A%22help+wanted%22) labels.
- **[CONTRIBUTING.md](CONTRIBUTING.md)** — dev setup, branch/PR conventions, and the non-negotiable schema rules for the offline-sync contract.

For significant changes (new models, new API surfaces, architectural decisions), open an issue to discuss the approach first; non-trivial features get a spec in `docs/spec/`.
