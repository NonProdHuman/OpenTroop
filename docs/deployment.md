# Deployment Guide

## Choosing a deployment target

OpenTroop is a Docker-first app: the backend is a standard FastAPI container,
the frontend will be a Next.js app, and the database is PostgreSQL.  Any
platform that can run Docker containers and a managed Postgres database works.

### Recommendation: Google Cloud Run + Cloud SQL

For a SaaS deployment that starts with a handful of troops and grows to
hundreds, **Cloud Run + Cloud SQL** is the best fit:

- **Cloud Run** — serverless containers that scale to zero when idle (zero
  compute cost overnight) and auto-scale horizontally under load.  No server
  management.
- **Cloud SQL (PostgreSQL)** — fully managed Postgres with automated backups,
  point-in-time recovery, and vertical scaling with a config change.

#### Cost at each growth stage

| Stage | Cloud Run | Cloud SQL tier | Est. monthly cost |
|-------|-----------|----------------|-------------------|
| Early beta (1–5 troops) | ~$0 (free tier) | `db-f1-micro` (0.6 GB) | **~$10–15** |
| Growing (5–50 troops) | ~$5–10 | `db-g1-small` (1.7 GB) | **~$30–40** |
| Scaled (50–500 troops) | ~$20–50 | `db-custom-2-7680` (2 vCPU / 7.5 GB) | **~$120–160** |

At 200 troops paying $5–10/month each, infrastructure is ~$150/month against
$1,000–2,000/month revenue — a healthy margin.

> **Cloud SQL minimum cost note:** Cloud SQL has a baseline charge even at
> zero traffic (~$7–9/month for `db-f1-micro`).  For pre-launch development,
> you can use a free Neon or Supabase Postgres instead and switch to Cloud SQL
> when you go live.

---

## Setting up Cloud Run + Cloud SQL

### Prerequisites

- A Google Cloud project with billing enabled.
- `gcloud` CLI installed and authenticated.
- Docker installed locally.

### Step 1 — Enable APIs

```bash
gcloud services enable \
  run.googleapis.com \
  sqladmin.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com
```

### Step 2 — Create a Cloud SQL instance

```bash
gcloud sql instances create opentroop-db \
  --database-version=POSTGRES_16 \
  --tier=db-f1-micro \
  --region=us-central1 \
  --storage-auto-increase

gcloud sql databases create opentroop --instance=opentroop-db
gcloud sql users create opentroop --instance=opentroop-db --password=<strong-password>
```

### Step 3 — Store secrets in Secret Manager

```bash
echo "postgresql+psycopg://opentroop:<password>@/<db>?host=/cloudsql/<project>:<region>:<instance>" \
  | gcloud secrets create DATABASE_URL --data-file=-

echo "https://<your>.clerk.accounts.dev/.well-known/jwks.json" \
  | gcloud secrets create AUTH_JWKS_URI --data-file=-
```

Repeat for `AUTH_ISSUER`, `AUTH_AUDIENCE`, `APP_DOMAIN`.

### Step 4 — Build and push the container

```bash
# From repo root
gcloud artifacts repositories create opentroop \
  --repository-format=docker --location=us-central1

docker build -t us-central1-docker.pkg.dev/<project>/opentroop/backend:latest backend/
docker push us-central1-docker.pkg.dev/<project>/opentroop/backend:latest
```

Or connect Cloud Run to a GitHub repo for automatic deploys on push.

### Step 5 — Deploy to Cloud Run

```bash
gcloud run deploy opentroop-backend \
  --image=us-central1-docker.pkg.dev/<project>/opentroop/backend:latest \
  --region=us-central1 \
  --platform=managed \
  --add-cloudsql-instances=<project>:us-central1:opentroop-db \
  --set-secrets=DATABASE_URL=DATABASE_URL:latest,AUTH_JWKS_URI=AUTH_JWKS_URI:latest \
  --allow-unauthenticated \
  --min-instances=0 \
  --max-instances=10
```

`min-instances=0` means the service scales to zero at night — no idle compute
cost.  Increase to `1` if cold-start latency matters for your use case.

### Step 6 — Run Alembic migrations

Cloud Run Jobs are the right tool for one-off commands like migrations:

```bash
gcloud run jobs create migrate \
  --image=us-central1-docker.pkg.dev/<project>/opentroop/backend:latest \
  --region=us-central1 \
  --add-cloudsql-instances=<project>:us-central1:opentroop-db \
  --set-secrets=DATABASE_URL=DATABASE_URL:latest \
  --command="uv,run,alembic,upgrade,head"

gcloud run jobs execute migrate --wait
```

Re-run this job after every deployment that includes a migration.

### Step 7 — Frontend on Vercel (or Cloud Run)

The Next.js frontend can be deployed to Cloud Run (as in Step 5 for the backend, but using the `frontend/Dockerfile` when we build it) or to Vercel for free:

1. Push the repo to GitHub.
2. Import the project at vercel.com.
3. Set the root directory to `apps/web/`.
4. Add environment variables: `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, the backend
   URL (`NEXT_PUBLIC_API_URL`), etc.

Vercel handles CDN, TLS, and preview deployments automatically.

### Step 8 — Seed the Superadmin

Once both your frontend and backend are deployed and the database is migrated:

1. Visit your deployed frontend application.
2. Sign in via Clerk.
3. Because the database is completely empty, **the first user to successfully authenticate is automatically granted the Platform `SUPERADMIN` role**.
4. You will be redirected to `/platform/tenants` where you can create your first tenant.

> **Note:** If you miss this window or need to grant superadmin to another user later, you can use the `promote_platform_admin.py` script via a Cloud Run job similar to Step 6.

---

## Tenant routing in production

The backend resolves the tenant from the request's `Host` header subdomain
(`troop123.opentroop.app`).  You need a wildcard DNS record pointing all
subdomains at Cloud Run, and a wildcard TLS certificate.

**DNS (in your registrar):**
```
*.opentroop.app  CNAME  ghs.googlehosted.com.
```

**Cloud Run domain mapping:**

```bash
gcloud beta run domain-mappings create \
  --service=opentroop-backend \
  --domain=api.opentroop.app \
  --region=us-central1
```

Cloud Run handles wildcard subdomains on custom domains — each troop's
subdomain automatically routes to the same Cloud Run service.  The backend
reads the `Host` header and does a single DB lookup to resolve `tenant_id`.

---

## Alternatives for early development

If you want to start immediately without Cloud billing setup:

| Platform | What it gives you | Approx. cost |
|----------|-------------------|-------------|
| **Railway** | Docker + managed Postgres, great DX | $5–20/month |
| **Render** | Docker + managed Postgres | $14/month (always-on) |
| **Fly.io** | Docker + Fly Postgres | $5–15/month |
| **Neon** (DB only) | Serverless Postgres, free tier | $0–19/month |

These are all fine for development and early beta.  Migrate to Cloud Run +
Cloud SQL when you're ready to go into production SaaS mode.

---

## Dockerfile (to be created)

The backend needs a `Dockerfile`.  A minimal example:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
RUN pip install uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./
EXPOSE 8080
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

> **Note:** The `Dockerfile` is not yet in the repo — this is the next step
> before any cloud deployment.
