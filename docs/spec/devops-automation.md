# DevOps & Infrastructure-as-Code Automation

**Status:** Draft
**Scope:** Infrastructure, Terraform, CI/CD Environments

---

## Overview

As OpenTroop is designed to support both a SaaS model and self-hosting for individual troops, setting up the required infrastructure (Google Cloud, Neon Database, Cloudflare DNS, Clerk Auth) manually is error-prone and scales poorly for ephemeral testing.

This specification outlines the transition to a fully automated **Infrastructure-as-Code (IaC)** pipeline using **Terraform**. This will allow developers or self-hosting troops to spin up or tear down a complete OpenTroop environment (database, frontend, backend, auth, and DNS) with a single command.

## Target Architecture

The goal is to maintain a `terraform/` directory in the repository containing declarative configurations for all required external services.

### 1. Google Cloud Platform (GCP)
**Provider:** `hashicorp/google`
- **Artifact Registry:** Automatically provision Docker image repositories for the frontend and backend.
- **Cloud Run:** Define the `opentroop-api` and `opentroop-web` services, specifying memory, CPU, scaling behavior (0 to N), and environment variables.
- **IAM & Workload Identity:** Automate the creation of service accounts and Workload Identity Federation pools, so GitHub Actions can deploy without relying on static, long-lived JSON keys.

### 2. Neon (Serverless Postgres)
**Provider:** `neon-database/neon`
- **Project & Compute:** Automatically provision the Neon project and the Postgres compute endpoint.
- **Roles:** Create the required database roles (e.g., the standard application role and the `BYPASSRLS` admin role for the control plane).
- **Environment Variables:** Terraform will extract the generated Neon connection strings and inject them directly into the GCP Cloud Run service definitions (`DATABASE_URL`, `DATABASE_URL_ADMIN`, `DATABASE_URL_MIGRATE`), eliminating the need to manually copy-paste secrets.

### 3. Cloudflare (DNS & Proxy)
**Provider:** `cloudflare/cloudflare`
- **DNS Records:** Automatically configure the wildcard `CNAME` (`*.opentroop.app`) and apex record to point to the newly provisioned Cloud Run frontend.
- **Cloudflare Workers:** (Optional) Deploy the Cloudflare Worker script that injects the `X-Forwarded-Host` header for wildcard subdomain routing if it's not possible to handle purely at the edge.

### 4. Clerk (Authentication)
**Provider:** API automation (via `terraform-provider-http` or custom script)
- While Clerk does not currently have an official 1.0 Terraform provider, its Management API is robust.
- Terraform can trigger API calls to provision a new Clerk application instance, extract the `PUBLISHABLE_KEY` and `SECRET_KEY`, and pipe them directly into the frontend and backend Cloud Run environments.

## The "One-Click" Workflow

With this automation in place, standing up a new OpenTroop environment requires only the following steps:

1. **Prerequisites:** A user provides API keys for GCP, Neon, Cloudflare, and Clerk in a local `terraform.tfvars` file.
2. **Deploy:** The user runs `terraform apply`.
3. **Execution:**
   - Terraform provisions Neon and extracts the DB URLs.
   - Terraform provisions Clerk and extracts Auth keys.
   - Terraform stands up GCP Artifact Registry and Cloud Run.
   - Terraform wires the secrets into Cloud Run and maps the Cloudflare DNS.
4. **Tear Down:** Once testing is complete, `terraform destroy` cleanly removes all resources, ensuring zero runaway costs for ephemeral staging environments.

## Integration with GitHub Actions
Once the IaC foundation is laid, it can be integrated into GitHub Actions to automatically spin up a completely isolated, full-stack OpenTroop environment (complete with its own database branch and subdomain) for every Pull Request, tearing it down when the PR is merged.
