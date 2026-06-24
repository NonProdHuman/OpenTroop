# Local Development Setup

Complete walkthrough from a fresh clone to a running stack with real data.

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| [uv](https://docs.astral.sh/uv/) | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Python | 3.12 | managed by uv — no manual install needed |
| [pnpm](https://pnpm.io) | 9+ | `npm install -g pnpm` |
| Node.js | 18+ | [nodejs.org](https://nodejs.org) |
| Docker Desktop | latest | [docker.com](https://www.docker.com) |

## 1. Clone and install

```bash
git clone https://github.com/NonProdHuman/OpenTroop.git
cd OpenTroop

# Frontend dependencies
pnpm install

# Backend dependencies
cd backend && uv sync && cd ..

# Install pre-commit hooks (one-time per clone)
uv tool install pre-commit --with pre-commit-uv
pre-commit install
```

## 2. Configure Clerk (auth)

1. Create a free project at [dashboard.clerk.com](https://dashboard.clerk.com).
2. Under **API Keys**, copy your publishable key and secret key.
3. Copy the example env file and fill in your keys:

```bash
cp apps/web/.env.local.example apps/web/.env.local
```

Edit `apps/web/.env.local`:

```env
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...
CLERK_SECRET_KEY=sk_test_...
```

Leave `NEXT_PUBLIC_TENANT_ID` blank for now — you'll fill it in after step 4.

## 3. Configure the backend

```bash
cp backend/.env.example backend/.env
```

Edit `backend/.env` and set the Clerk values to match your frontend project.
The JWKS URI and issuer come from your Clerk publishable key — run this to derive them:

```bash
python3 -c "
import base64, sys
k = open('apps/web/.env.local').read()
key = next(l.split('=',1)[1].strip() for l in k.splitlines() if l.startswith('NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY'))
raw = key.split('_',2)[2]; raw += '=' * (-len(raw) % 4)
host = base64.b64decode(raw).decode().rstrip('\$')
print(f'AUTH_ISSUER=https://{host}')
print(f'AUTH_JWKS_URI=https://{host}/.well-known/jwks.json')
"
```

## 4. Sign in first, then provision your tenant

> **Critical:** you must sign in before running `provision-tenant`. The script
> auto-links the founding admin to whichever Clerk account signed in. If you
> provision first, all API calls will return 403.

Start the full stack:

```bash
./start.sh
```

Open **http://localhost:3000** and sign in with Clerk. This creates your `User`
row in the database. Then provision your tenant (a "tenant" is your troop):

```bash
cd backend
uv run provision-tenant \
  --troop-name "Troop 123" \
  --slug troop123 \
  --admin-first Your \
  --admin-last Name
```

The script prints your new **Tenant ID** and confirms the Clerk link:

```
Tenant created: 'Troop 123'
  Tenant ID : xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
  Admin     : Your Name (member id: …)
  Linked to : user id …  ✓ ready to use
```

If you see `Linked to : (none)` instead, the script will print the exact
`link-admin` command to run — copy and run it, then continue.

Add the Tenant ID to `apps/web/.env.local`:

```env
NEXT_PUBLIC_TENANT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

Restart `./start.sh` to pick up the env change.

The `--slug` becomes the future subdomain (`troop123.opentroop.app`). Lowercase
letters, digits, and hyphens only.

## 5. Import TroopWebHost data (optional)

If you have a TWH full-data XML export:

```bash
cd backend
uv run import-twh <tenant-id> path/to/export.xml
```

The file path is relative to `backend/`. The tenant ID comes from step 4.

> **Note:** Real and anonymized TWH exports are blocked from being committed
> (see `reference/.gitignore`). Keep export files outside the repo.

## 6. Start the web app

From the **repo root**:

```bash
pnpm dev
```

Open [http://localhost:3000](http://localhost:3000). Sign in with Clerk — the app
will use your `NEXT_PUBLIC_TENANT_ID` to scope all API calls to your troop.

---

## Re-import workflow

When iterating on the TWH importer, you don't need to tear down the whole
database. Instead, clear just the imported data and re-run:

```bash
cd backend

# Clear imported data — keeps your Clerk-linked admin account intact
uv run reset-tenant <tenant-id>

# Re-import
uv run import-twh <tenant-id> path/to/export.xml
```

## Full reset

To wipe the database entirely and start over (loses all data):

```bash
cd backend
uv run reset-db
```

Then repeat from step 4.

---

## Connecting Clerk identity to an imported member

After importing, your founding admin member (created by `provision_tenant.py`)
and any matching imported member are separate rows. To merge them — linking your
Clerk sign-in to the full imported member record — use the invite/claim flow:

1. As admin, call `POST /members/{imported-member-id}/invite` to get a claim token.
2. Sign in via Clerk, then call `POST /auth/claim` with the token.

This links your `User.id` to the imported member row.
*(A UI for this flow is on the roadmap.)*

---

## Summary of dev scripts

All run from `backend/`:

| Command | Purpose |
|---------|---------|
| `uv run anonymize-twh <real.xml> <out.xml>` | Scrub PII from a real TWH export to produce a safe test fixture |
| `uv run provision-tenant --troop-name … --slug … --admin-first … --admin-last …` | Create a new tenant + admin member + event type defaults; auto-links to your Clerk identity if you signed in first |
| `uv run promote-platform-admin --email you@example.com` | Grant a signed-in user the global **platform-admin** role (needed to create tenants via `POST /tenants/`); `--revoke` to remove |
| `uv run import-twh <tenant-id> <file>` | Import a TWH XML export into an existing tenant |
| `uv run reset-tenant <tenant-id>` | Clear imported data for one tenant (keep admin) |
| `uv run reset-db` | Nuclear: drop all tables + re-migrate |
