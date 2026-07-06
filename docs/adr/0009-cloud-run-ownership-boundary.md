# 0009. Cloud Run ownership: Terraform provisions the shell, GitHub Actions owns the image

- **Status:** Accepted
- **Date:** 2026-07-06

## Context

Two systems both write to the production Cloud Run services and were fighting:

- **Terraform/Scalr** declares `google_cloud_run_v2_service.{api,web}` with
  `image = var.api_image` / `var.web_image` (`terraform/gcp.tf`). On every
  `terraform apply` it reconciles the image back to the tfvars value.
- **GitHub Actions** (`deploy.yml`) builds a `:<sha>` image on each push to `main`
  and rolls it onto the same service via `deploy-cloudrun`.

So after a deploy, the next `terraform apply` would revert the service to the
bootstrap image unless someone hand-synced tfvars to the last-deployed SHA.
Separately, `deploy.yml` defaulted to flat service names (`opentroop-api`,
`opentroop-web`) when its GitHub variables were unset, while Terraform names
services `opentroop-<env>-api/-web` — so an unconfigured prod deploy created new,
hand-managed services *alongside* the Terraform-managed ones. No ADR named who
owns what, and the two Draft devops specs still described the flat names and a
GHCR registry the real pipeline never used.

## Decision

**Split ownership by concern:**

- **Terraform/Scalr owns the service *shell* and everything declarative about it** —
  existence, name, region, scaling, service account, IAM, ingress, env vars, and
  Secret Manager wiring. It **provisions** the service and sets a **bootstrap**
  image only at first create.
- **GitHub Actions owns the running *image/revision*.** After bootstrap, each push
  to `main` builds and rolls a new revision.
- Terraform **stops reconciling the image**: both services carry
  `lifecycle { ignore_changes = [template[0].containers[0].image] }`. `var.api_image`
  / `var.web_image` are bootstrap-only; `terraform plan` shows no image diff after a
  deploy.
- **`deploy.yml` fails the production job** if `GCP_PROJECT_ID`,
  `GCP_API_SERVICE_NAME`, `GCP_WEB_SERVICE_NAME`, or `GCP_ARTIFACT_REPOSITORY` are
  unset, rather than falling back to the flat `opentroop-*` names that mint orphan
  services. Prod must target the Terraform outputs (`opentroop-<env>-*`).

## Consequences

- `terraform apply` and GitHub deploys no longer contend for the image field.
- Production can only deploy to the Terraform-provisioned services; the flat-named
  hand-created services are retired (operator step in #220).
- **Cost:** the image shown in Terraform state goes stale (it stays at the bootstrap
  value) — intentional; the live revision is authoritative and visible in Cloud Run
  / the deploy logs, not in tfvars. Rolling back is a redeploy (GitHub Actions), not
  a `terraform apply`.
- The Draft `docs/spec/devops-automation.md` and `devops-gitops-restructuring.md`
  (flat names, GHCR) are superseded by this boundary and the actual pipeline.

## Alternatives considered

- **Let Terraform own the image too** (CI writes the deployed SHA back to tfvars/a
  data source each deploy). Rejected: couples every app deploy to a Terraform run and
  a state write; slow, and a broken TF plan blocks shipping.
- **Let GitHub Actions own the whole service** (create + configure via `gcloud`).
  Rejected: loses declarative infra, IAM, and secret wiring; that is exactly what
  Scalr/Terraform is for.
- **Align the names but keep both writing the image.** Rejected: fixes the orphan-
  services half but leaves the apply-reverts-deploy fight.
