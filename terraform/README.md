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
