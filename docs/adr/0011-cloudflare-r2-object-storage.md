# 0011. Object storage: Cloudflare R2 via an S3-compatible driver

- **Status:** Accepted
- **Date:** 2026-07-06

## Context

The event-linked photo gallery (#145) is the platform's first binary-media
feature, and the Resources document library (#144) will be the second. Neither
can store bytes in Postgres (galleries are hundreds of multi-hundred-KB objects
per event) or on Cloud Run's ephemeral filesystem. #144's issue text suggested
"a GCS bucket per the existing GCP deployment", but no storage decision was ever
actually made — no ADR, no spec, no code.

Two forces dominate:

- **Photo serving is egress-heavy.** The same campout album is opened dozens of
  times and re-downloaded to camera rolls on both web and mobile. On GCS or AWS
  S3, per-GB egress is the dominant recurring cost of a photo product at SaaS
  scale (200+ troops), and it scales with *views*, not uploads — the axis we
  least control.
- **Photo bytes must not transit the API.** Cloud Run bills on request time and
  concurrency; proxying uploads/downloads through FastAPI would make the
  cheapest requests the most expensive. The flow must be presigned-URL direct:
  client → bucket on upload, bucket → client on download.

## Decision

**We use Cloudflare R2, accessed exclusively through its S3-compatible API,
behind the pluggable `StorageService` driver in `app/core/storage.py`.**

- The backend is selected once via `STORAGE_BACKEND` (`r2`/`s3`/`gcs` share the
  one S3-compatible driver; `fake` is the in-memory test/dev backend; `none`
  fails loud), mirroring `EMAIL_BACKEND`/`PUSH_BACKEND`. App code never imports
  a cloud SDK directly.
- Object keys are namespaced per tenant — `<tenant_id>/photo/<photo_id>/…` —
  mirroring the `tenant_id` partition key so one troop's objects are isolated
  and a tenant purge (ADR 0010) is a prefix delete.
- **No object is ever public.** Every read is a short-lived presigned GET minted
  per authorized request; every write a short-lived presigned PUT minted after a
  quota reservation. The bucket has no public access.
- The server trusts only its own `HEAD` of the object (never the client's
  claimed size) when confirming quota accounting on `Tenant.used_storage_bytes`.
- #144 (Resources) inherits this substrate as-is: same driver, same key
  namespace pattern (`<tenant_id>/resource/…`), same presign rules.

## Consequences

- **$0 egress** removes the dominant cost axis; storage (~$0.015/GB-month) and
  per-operation charges remain, both bounded by the per-tenant quota meter.
- Cloudflare is already our edge (Worker, WAF, rate limiting — GH-116/117), so
  R2 adds no new vendor and can later serve thumbnails via Cloudflare Image
  Resizing without a server-side image worker.
- Because we speak only the S3 API, self-hosters can point the same driver at
  MinIO, AWS S3, or GCS interop — the R2 choice is an env var, not a code fork.
- Cost we accept: R2 has no native lifecycle-to-cold-tier equivalent of S3
  Glacier, and Cloudflare Image Resizing is a paid, Cloudflare-only dependency —
  self-host degrades to server-side thumbnails.
- boto3 joins the backend dependencies (presigning is offline; only
  `head`/`delete` call the network).

## Alternatives considered

- **Google Cloud Storage** (#144's hint; the API already runs on Cloud Run):
  keeps one cloud, but per-GB egress on every gallery view makes the
  view-heavy photo workload structurally expensive, and GCS's S3-interop mode
  means even "choose GCS" still speaks the S3 API — so we lose nothing by
  defaulting to R2 and keeping GCS a config value.
- **AWS S3:** the reference implementation, but a third vendor we don't
  otherwise use, with the same egress problem.
- **Postgres bytea / Cloud SQL:** binary blobs in the OLTP database bloat
  backups, WAL, and Neon storage; a non-starter at album scale.
- **Proxying bytes through FastAPI** (any backend): doubles egress, ties up
  Cloud Run instances on large transfers, and adds nothing — presigned URLs
  are the industry-standard direct path.
