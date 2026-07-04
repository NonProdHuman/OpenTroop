# OpenTroop

A modern, mobile-first, open-source troop management platform.

OpenTroop is designed to support the complex operational needs of scouting units. Our early focus is providing robust **Event Management** and **Communication** tools, with Advancement and Reporting planned for future phases. Built **offline-first**, it ensures that leaders can continue working seamlessly at camps or in the wilderness without cellular service. Every data record is designed for background synchronization (using client-generatable UUIDv7 keys, per-row timestamps, and soft-delete tombstones) and is securely partitioned by `tenant_id` to support robust multi-tenant SaaS deployments as well as self-hosted troops.

## Features & Roadmap

OpenTroop is being built in phases to ensure a strong foundation before moving to complex domains:

- ✅ **Roster & Relationships:** Full membership modeling, family relationships, Groups/Patrols, and a robust Role-Based Access Control (RBAC) system.
- ✅ **Multi-Tenant Isolation:** Deep isolation via PostgreSQL Row-Level Security, allowing safe scaling from one troop to hundreds on a shared platform.
- 🚧 **Events & Calendar:** (In Progress) Event types, RSVP, capacity limits, attendance, permission slips, and personalized iCal feeds.
- 🚧 **Communications:** (In Progress) A vendor-agnostic notification service already delivers invite emails and event-triggered notifications (creation, cancellation, permission slips); async send queue, SMS, and targeted group announcements are next.
- 🚧 **Advancement:** (In Progress — core shipped) Versioned rank-requirement catalog, merit badges, report→approve workflow, and automatic credit from event attendance, with live progress meters and an approval queue. Scoutbook CSV sync is the remaining piece.
- 🧊 **Mobile Apps:** Native iOS & Android apps providing full offline-first capabilities.

For more details on the phases, see our [ROADMAP.md](ROADMAP.md).

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
            R_IMPORT["Data Import<br/>(XML/CSV)"]
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

## Getting Started

To try out OpenTroop locally, you can use the unified start script which brings up the entire stack using Docker and local development servers:

```bash
./start.sh
```

This validates your configuration, starts Postgres via Docker, runs the FastAPI backend with uvicorn, and launches the Next.js dev server. See [docs/local-setup.md](docs/local-setup.md) for the full first-time setup walkthrough, including creating a Clerk application for authentication.

## Local Development

OpenTroop uses a monorepo structure.

### Frontend
Located in `apps/web/`. Requires [pnpm](https://pnpm.io) and Node 22.13+.

```bash
pnpm install                                         # install all workspace deps
cp apps/web/.env.local.example apps/web/.env.local   # add auth keys
pnpm dev                                             # start web app on :3000
```

### Backend
Located in `backend/`. Requires [uv](https://docs.astral.sh/uv/) and Python 3.12.

```bash
uv sync                                              # create .venv/ and install all deps
uv run pytest                                        # run the test suite (no database needed)
uv run uvicorn app.main:app --reload                 # start the API on :8000
```

### Dev Verification Loop
With the stack running, seed a deterministic dev tenant and run the Playwright smoke suite:

```bash
uv run seed-dev-data          # from backend/ — idempotent dev tenant + sample data
pnpm --filter web e2e         # Playwright smoke tests against the running app
```

### Pre-commit Hooks
We rely on pre-commit to keep code quality high.

```bash
uv tool install pre-commit --with pre-commit-uv
pre-commit install
pre-commit run --all-files
```

## Deployment

See **[docs/deployment.md](docs/deployment.md)** for a full guide.
The recommended production setup is **Google Cloud Run + Cloud SQL**, which offers a fully managed, auto-scaling environment well-suited to handle multiple tenants easily.

## Contributing

OpenTroop is developed in the open and welcomes contributors! Check out the [CONTRIBUTING.md](CONTRIBUTING.md) guide for information on code standards, branch conventions, and how to get started on your first issue. We actively tag tasks that are great for newcomers with the `good first issue` label.
