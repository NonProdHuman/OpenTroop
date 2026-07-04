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
creates Cloud Run services from container images. Once the services and Artifact
Registry repository exist, the GitHub Actions deploy workflow can push and roll
forward new images.

After apply, copy these outputs into GitHub repository variables or secrets if
you continue using the checked-in deploy workflow:

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
