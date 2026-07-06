# OpenTroop Terraform

This directory provisions the first automated OpenTroop environment described in
`docs/spec/devops-automation.md`:

- Google Artifact Registry for backend and frontend images
- Cloud Run services for the API and web app, named per environment by default
- Secret Manager runtime configuration
- GitHub Actions Workload Identity Federation, with no JSON keys
- Neon Postgres project, branch, owner role, and app login role
- Cloudflare DNS records and Worker proxy for wildcard tenant routing
- Optional Clerk JWT-template automation for the `email` claim

## Provider note

The draft spec names `neon-database/neon`, but that provider namespace is not
published in Terraform Registry. This implementation uses the maintained
community provider `kislerdm/neon`, which exposes the generated Neon connection
URI Terraform needs to wire Cloud Run.

## Usage

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# edit terraform.tfvars
terraform init
terraform apply
```

The initial `api_image` and `web_image` must already exist because Terraform
creates Cloud Run services from container images. They are **bootstrap-only**:
both services set `lifecycle { ignore_changes = [template[0].containers[0].image] }`,
so once the service exists the **GitHub Actions deploy workflow owns the running
image/revision** and `terraform apply` will not revert it. Terraform owns the
service shell (name, scaling, IAM, env, secrets); Actions owns the image. See
[ADR 0009](../docs/adr/0009-cloud-run-ownership-boundary.md).

After apply, copy these outputs into GitHub **environment** variables (set them on
the `production` environment — the deploy workflow now *requires* them there and
fails rather than falling back to flat `opentroop-*` service names):

- `GCP_PROJECT_ID`
- `GCP_REGION`
- `GCP_SERVICE_ACCOUNT`
- `GCP_WORKLOAD_IDENTITY_PROVIDER`
- `GCP_ARTIFACT_REPOSITORY`
- `GCP_API_SERVICE_NAME`
- `GCP_WEB_SERVICE_NAME`
- `API_PUBLIC_URL` or `NEXT_PUBLIC_API_URL`

## Edge security rollout (GH-116 / GH-117)

The edge belts are code-complete but staged behind variables so they can be
enabled deliberately. Suggested order:

1. **Origin shared secret — on by default with Cloudflare.** The next apply
   generates `ORIGIN_SHARED_SECRET`, binds it to the Worker (which stamps
   `X-Origin-Auth` on every proxied request), and sets it in the API's Secret
   Manager config. Once both the Worker and a new API revision are deployed,
   direct `*.run.app` requests get 403 and `TRUST_FORWARDED_HOST=true` is fully
   sound. Order matters only in the harmless direction: an API revision with the
   secret set will reject traffic from an old Worker, so apply Terraform (the
   Worker updates immediately) **before** the next API deploy picks up the env.
2. **`ALLOW_TENANT_ID_HEADER=false`** is set automatically when
   `cloudflare_enabled` — tenant resolution becomes subdomain-only in SaaS.
   Self-host/direct deployments keep the header.
3. **App-layer rate limiting** (`api_rate_limit_enabled`, default `true`) —
   in-process fixed windows: per-tenant on authenticated routes, per-IP on
   `/calendar/*` and `/auth/*`. Tune via the `RATE_LIMIT_*` env vars if needed.
4. **Cloudflare WAF** (`cloudflare_waf_enabled = true`) — deploys the Cloudflare
   Managed + OWASP Core rulesets. **Requires Pro plan.** Watch Security → Events
   for false positives before tightening.
5. **Cloudflare rate-limiting rules** (`cloudflare_rate_limit_enabled = true`) —
   per-IP edge limits on the calendar feed (60/min), auth plane (20/min), and
   import path (5/min). **Plan limits apply** (Free = one rule with 10s periods;
   the shipped values assume Pro).
6. **Cloudflare Access on the control plane** (`cf_access_enabled = true`, plus
   `cf_access_team_domain` and `cf_access_allowed_emails`) — creates the Access
   application covering `admin.<domain>` and the `/platform` API paths, and wires
   `CF_ACCESS_TEAM_DOMAIN` / `CF_ACCESS_AUD` into the API, which then requires a
   valid `Cf-Access-Jwt-Assertion` on every `/platform/*` request in addition to
   the platform-role check. Requires a Zero Trust team (free tier is fine).
   After apply, set the Access application's **cookie domain to the parent
   domain** in the Zero Trust dashboard so the admin console's XHR calls to
   `api.<domain>` carry the Access session.

## Async import worker (GH-240)

Large TWH imports can exceed Cloud Run's request timeout, so on SaaS an import is
pushed to a **Cloud Tasks queue** that invokes a dedicated **worker Cloud Run
service** (same image, `timeoutSeconds` 3600, scales to zero). Enable it with:

```hcl
import_queue_backend = "cloudtasks"   # default "inprocess" (self-host/dev)
```

When set, `terraform apply` provisions the `cloudtasks.googleapis.com` API, an
`<prefix>-imports` queue, an `<prefix>-import-worker` service + its service
account, and the IAM (the API SA gets `cloudtasks.enqueuer` on the queue and
`actAs` on the worker SA; the worker SA gets `run.invoker` on the worker and
secret access). The API's `IMPORT_*` env is wired automatically.

Two operator follow-ups:

- **Set `GCP_IMPORT_WORKER_SERVICE_NAME`** in the deploy workflow's GitHub
  environment to the `import_worker_service_name` output. The worker runs the same
  backend image, so the deploy workflow must roll it alongside the API — the step
  is skipped when the variable is empty.
- **Deterministic URL check.** The worker carries its own URL as the OIDC audience,
  computed as `https://<service>-<project_number>.<region>.run.app`. If your
  project uses legacy hashed Cloud Run URLs the apply fails with a postcondition
  telling you the actual URI — set `import_worker_url` to it and re-apply.

The default (`inprocess`) creates none of this: the API drains queued jobs in a
background loop / the `drain-import-jobs` CLI (self-host needs **CPU always
allocated** if draining in-process on Cloud Run).

## Photo storage (R2) + weekly maintenance job (GH-145, ADR 0011)

Event photos live in **Cloudflare R2**, spoken through the S3-compatible API.
Step-by-step dashboard instructions (R2 enablement, API token, **CORS policy —
required for browser uploads**) live in [`docs/r2-setup.md`](../docs/r2-setup.md).
Enable storage with:

```hcl
storage_backend           = "r2"
manage_r2_bucket          = true   # or supply an existing bucket via storage_bucket
storage_access_key_id     = "..."  # an R2 API token's S3 key pair — created in the
storage_secret_access_key = "..."  # Cloudflare dashboard; the provider can't mint these
```

Terraform then creates the `<prefix>-media` R2 bucket (private — the backend
mints short-lived presigned URLs for every access), derives the endpoint from
`cloudflare_account_id`, wires `STORAGE_*` env onto the API service, and stores
the key pair in Secret Manager.

A **weekly maintenance Cloud Run Job** (`<prefix>-maintenance`, on by default via
`maintenance_job_enabled`) runs `reap-photo-uploads && reap-tombstones` —
releasing abandoned upload reservations, deleting soft-deleted photos' objects,
and hard-deleting purged-member tombstones past retention. **Cloud Scheduler**
triggers it on `maintenance_schedule` (default `0 8 * * 1`, Mondays 08:00 UTC);
both reapers are idempotent and cumulative, so a missed week self-heals.

One operator follow-up, mirroring the import worker (ADR 0009): **set
`GCP_MAINTENANCE_JOB_NAME`** in the deploy workflow's GitHub environment to the
`maintenance_job_name` output so deploys roll the job's image; Terraform only
bootstraps it. Self-host deployments can set `maintenance_job_enabled = false`
and run both CLIs from their own cron instead.

## Scalr Workspaces

Use separate Scalr workspaces and state for dev and prod. Keep secrets, Neon
projects, Clerk applications, and Cloud Run services separate between them.

Production workspace example:

```hcl
environment          = "prod"
app_domain           = "opentroop.app"
cloudflare_zone_name = "opentroop.app"
```

Development workspace example:

```hcl
environment          = "dev"
app_domain           = "dev.opentroop.app"
cloudflare_zone_name = "opentroop.app"
```

With those values, Terraform derives distinct default names:

| Setting | Prod | Dev |
| --- | --- | --- |
| Web URL | `opentroop.app` | `dev.opentroop.app` |
| Tenant URL | `troop123.opentroop.app` | `troop123.dev.opentroop.app` |
| API URL | `api.opentroop.app` | `api.dev.opentroop.app` |
| Cloud Run API | `opentroop-prod-api` | `opentroop-dev-api` |
| Cloud Run Web | `opentroop-prod-web` | `opentroop-dev-web` |
| Artifact Registry | `opentroop-prod-containers` | `opentroop-dev-containers` |

You can override `api_service_name`, `web_service_name`, or
`artifact_repository_name` if you need legacy names.

## Database URLs

When `manage_neon = true`, Terraform creates:

- `opentroop_owner`, the Neon default owner role
- `opentroop_app`, the login role used for normal tenant traffic

`DATABASE_URL` defaults to the `opentroop_app` URL. `DATABASE_URL_ADMIN` and
`DATABASE_URL_MIGRATE` default to the owner URL. For stricter SaaS deployments,
override those three variables with role-specific URLs once your Neon/Postgres
role bootstrap policy is finalized.

## Clerk

Set `manage_clerk_jwt_template = true` to create/update a custom Clerk JWT
template named `opentroop` with:

```json
{"email":"{{user.primary_email_address}}"}
```

The web app requests that template through `NEXT_PUBLIC_CLERK_JWT_TEMPLATE`,
which keeps the default Clerk session-token behavior unchanged when the variable
is empty.

## Cloudflare

Terraform creates proxied records for:

- `opentroop.app`
- `*.opentroop.app`
- `api.opentroop.app`

For nested environments such as `dev.opentroop.app`, set
`cloudflare_zone_name = "opentroop.app"`. Terraform then creates `dev`,
`*.dev`, and `api.dev` records in that zone.

The Worker forwards traffic to the raw Cloud Run URL and injects
`X-Forwarded-Host` so tenant subdomain routing can use the original host.

When `cloudflare_enabled = false`, add the generated web Cloud Run URL to
`cors_origins` on a follow-up apply if you need browser access through the raw
`run.app` hostname.
