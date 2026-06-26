# Hosting & Deployment Spec

**Status:** Draft
**Scope:** Infrastructure, CI/CD, Production Topology
**Pillars:** Architecture Foundation

---

## Overview

This specification defines the initial production infrastructure and continuous deployment (CI/CD) pipeline for OpenTroop. The chosen architecture prioritizes a near-$0 monthly cost during development and early beta testing, while establishing a robust, scalable "Modern Serverless" foundation that can handle massive traffic and multi-tenant isolation out of the box.

The core technology stack consists of:
1. **Google Cloud Run** for stateless, auto-scaling compute (FastAPI backend and Next.js frontend).
2. **Neon Serverless Postgres** for the RLS-compatible relational database.
3. **GitHub Actions** for automated, push-to-deploy CI/CD.

## Target Architecture

We are deploying a split-tier architecture where the frontend and backend run as independent services. This enforces a strict API contract, enables independent scaling, and mirrors the future state where mobile applications will communicate directly with the backend.

### 1. Database: Neon Serverless Postgres

Neon provides a fully managed, serverless Postgres environment.

- **Capabilities:** Full Postgres compatibility, including Row-Level Security (RLS) policies essential for OpenTroop's multi-tenant SaaS model.
- **Cost Efficiency:** Compute scales to zero during inactivity. The free tier comfortably supports development and initial small-scale deployments.
- **Workflow Integrations:** Database branching allows us to spin up isolated database environments per Pull Request, enabling destructive schema tests without impacting the primary database.

### 2. Compute: Google Cloud Run (GCP)

Cloud Run will host both our backend and frontend as distinct serverless containers.

- **`opentroop-api` (Backend):** A containerized instance of the FastAPI application.
- **`opentroop-web` (Frontend):** A containerized instance of the Next.js application.

**Key Advantages:**
- **Cost:** Generous free tier (2 million requests/month) ensures $0 compute costs during development.
- **Scale-to-Zero:** Instances spin down completely when not receiving traffic.
- **Stateless:** Enforces best practices; the applications must not rely on local file system state, which perfectly aligns with OpenTroop's architecture.
- **Security:** Easily integrate with Google Secret Manager for environment variables and secrets (like Clerk API keys or Neon connection strings).

## Deployment Pipeline (CI/CD)

Deployments will be fully automated via GitHub Actions. Merging code to the `main` branch will trigger the production deployment workflow.

### Sequence of Operations

1. **Trigger:** Push to `main`.
2. **Authentication:** Authenticate GitHub Actions to Google Cloud using **Workload Identity Federation**.
   * *Security Note:* We will **not** generate or store long-lived JSON service account keys in GitHub Secrets. Workload Identity uses short-lived OIDC tokens.
3. **Build Backend Container:**
   * Run tests and linters.
   * Build the Docker image for the FastAPI app.
   * Push the image to Google Artifact Registry (GAR).
4. **Database Migration:**
   * Run an ephemeral job that connects to the Neon database and executes `alembic upgrade head`.
5. **Deploy Backend:**
   * Update the `opentroop-api` Cloud Run service with the new image.
6. **Build & Deploy Frontend Container:**
   * Build the Next.js Docker image.
   * Push to GAR.
   * Update the `opentroop-web` Cloud Run service.

## Configuration & Secrets Management

Secrets will not be baked into containers.
- **GitHub Secrets:** Will only hold configuration needed for the CI/CD pipeline (e.g., GCP Project ID, Workload Identity Provider name).
- **GCP Secret Manager:** Will hold runtime secrets (Database URL, Clerk Secret Keys). Cloud Run services will securely resolve these at startup.

## Local vs. Production Parity

While production runs on Cloud Run and Neon, local development will continue to use standard Docker Compose (`start.sh`) with a local Postgres container. The code executing in the Cloud Run containers is identical to the code running locally, differing only via environment variables mapping to the managed services.

## DNS & Multi-Tenant Routing (Cloudflare)

OpenTroop uses a dynamic subdomain model (`[tenant-slug].opentroop.app`). Because GCP Cloud Run does not natively support wildcard domain mappings without an expensive load balancer, we use **Cloudflare** as a reverse proxy to handle routing at $0/month.

### Architecture
1. **DNS Records:**
   * A wildcard `CNAME` record (`*.opentroop.app`) and apex record (`opentroop.app`) point to Cloudflare.
2. **Cloudflare Worker (The Proxy):**
   * A free Cloudflare Worker intercepts requests to the apex domain and all subdomains.
   * It rewrites the destination URL to point to the raw Cloud Run URL (`https://opentroop-web-xxxxx.run.app`).
   * **Crucially**, it injects an `X-Forwarded-Host` header containing the original domain (e.g., `troop666.opentroop.app` or `opentroop.app`).
3. **Application Routing:**
   * The Next.js frontend and FastAPI backend read the `X-Forwarded-Host` header to determine the tenant context.
   * If the host is the apex domain (`opentroop.app`), the frontend serves the global landing page, auth flow, and tenant picker dashboard.
   * If the host is a tenant subdomain, it serves the troop-specific application.
