# Cloudflare R2 Setup for Event Photos (GH-145, ADR 0011)

Event photos live in a **private** Cloudflare R2 bucket, accessed exclusively
through short-lived presigned URLs the backend mints — there is no public-read
configuration anywhere in this guide, by design. This walks through the manual
Cloudflare-dashboard steps Terraform cannot do for you, then the Terraform and
GitHub wiring.

Companion docs: [`terraform/README.md`](../terraform/README.md) ("Photo storage
+ weekly maintenance job"), [ADR 0011](adr/0011-cloudflare-r2-object-storage.md).

---

## Step 1 — Enable R2 on the Cloudflare account

1. Log in to the [Cloudflare dashboard](https://dash.cloudflare.com) and select
   the account that owns the `opentroop` zone.
2. In the left sidebar, open **R2 Object Storage**.
3. First use requires accepting the R2 terms and **adding a payment method**,
   even on the free tier (10 GB storage, 1M class-A + 10M class-B operations
   per month free; **egress is always $0**).
4. Note your **Account ID** (right sidebar of any zone page, or the R2 overview
   URL) — it should already be set as `cloudflare_account_id` in the Terraform
   workspace; the S3 endpoint derives from it:
   `https://<account-id>.r2.cloudflarestorage.com`.

## Step 2 — Create the R2 API token (the S3 key pair)

The backend and the maintenance job authenticate to R2 with an S3-style key
pair. Cloudflare mints these from an **R2 API token** — this cannot be done by
the Terraform provider, so it is always a dashboard step.

1. In **R2 Object Storage**, click **API** (top right) → **Manage API tokens**
   → **Create Account API token**.
   (Use an *Account* API token, not a *User* token — it survives personnel
   changes.)
2. Name it per environment, e.g. `opentroop-prod-media`.
3. **Permissions:** `Object Read & Write`.
4. **Bucket scope:** *Apply to specific buckets only* → select the media bucket
   (create it first via Step 3/Terraform, or temporarily scope to
   *all buckets* and tighten after the first apply). Never grant Admin
   Read & Write — the app only needs object CRUD.
5. Optional but recommended: no TTL (rotate manually), no client-IP filter
   (Cloud Run egress IPs vary).
6. Click **Create API Token**, then copy from the confirmation screen:
   - **Access Key ID** → `storage_access_key_id`
   - **Secret Access Key** → `storage_secret_access_key`
   These are shown **once**. Store them in the Terraform workspace (Scalr) as
   *sensitive* variables — Terraform then places them in GCP Secret Manager for
   the runtime; they never go in `.env` files or GitHub.

> Rotation: create a second token, apply the new pair via Terraform, verify an
> upload works, then delete the old token in the dashboard.

## Step 3 — Bucket (Terraform-managed or bring-your-own)

Preferred: let Terraform own it. In the workspace variables:

```hcl
storage_backend           = "r2"
manage_r2_bucket          = true          # creates <name-prefix>-media
storage_access_key_id     = "…"           # sensitive
storage_secret_access_key = "…"           # sensitive
```

The Terraform `cloudflare_api_token` (the one the provider itself uses) must
include the **Workers R2 Storage: Edit** account permission for
`manage_r2_bucket = true` — extend the existing token or recreate it with that
permission added. Alternatively, create the bucket by hand in the dashboard
(**R2 → Create bucket**, default settings, location *Automatic*) and set
`storage_bucket = "<its-name>"` with `manage_r2_bucket = false`.

Leave all public-access options **off** (no public bucket URL, no custom
domain). Presigned URLs are the only access path.

## Step 4 — CORS policy on the bucket (required for web uploads)

The web app PUTs photo bytes **directly to the bucket** from the browser and
renders gallery images from presigned GETs — both are cross-origin requests, so
the bucket needs a CORS policy. (Mobile uploads are native HTTP and unaffected.)

Dashboard: **R2 → \<bucket\> → Settings → CORS policy → Add CORS policy**, and
paste (adjust the domain for the environment):

```json
[
  {
    "AllowedOrigins": [
      "https://opentroop.app",
      "https://*.opentroop.app"
    ],
    "AllowedMethods": ["GET", "PUT"],
    "AllowedHeaders": ["content-type"],
    "MaxAgeSeconds": 3600
  }
]
```

For local development against a real bucket, add `http://localhost:3000` and
`http://*.localhost:3000` to `AllowedOrigins` (or use `STORAGE_BACKEND=fake`,
which needs no bucket at all).

Symptom of a missing policy: uploads fail in the browser console with a CORS
preflight error on `…r2.cloudflarestorage.com`, while the same upload from the
mobile app succeeds.

## Step 5 — Apply and wire the deploy workflow

```bash
cd terraform
terraform apply
```

The apply creates the bucket (if managed), the `STORAGE_*` env on the API
service, the Secret Manager secrets for the key pair, and the **weekly
maintenance Cloud Run Job + Scheduler** (reapers; Mondays 08:00 UTC by
default — `maintenance_schedule` to tune).

Then copy one new output into the GitHub **environment** variables (same place
as the `GCP_*` values, per [ADR 0009](adr/0009-cloud-run-ownership-boundary.md)):

- `GCP_MAINTENANCE_JOB_NAME` = the `maintenance_job_name` output

Deploys now roll the maintenance job image alongside the API; leaving the
variable unset skips the step (self-host cron mode).

## Step 6 — Verify

1. Deploy (push to the deploy branch) so the API picks up the new env/secrets.
2. In the web app, open an event → **Photos** → **Add photos**, upload one.
   It should appear in the grid, and **R2 → \<bucket\> → Objects** should show
   `<tenant-id>/photo/<photo-id>/display.jpg`.
3. Check the meter: `GET /storage/usage` (or the "storage left" caption in the
   uploader) reflects the upload.
4. Run the maintenance job once by hand and check its logs:

   ```bash
   gcloud run jobs execute <maintenance-job-name> --region <region> --wait
   ```

   Expected output ends with `Reaped 0 stale pending upload(s), purged 0
   deleted photo(s)` on a fresh install.

## Self-host / no Cloudflare

Any S3-compatible store works: set `STORAGE_BACKEND=s3` (or `gcs` with GCS's
S3-interop HMAC keys), `STORAGE_BUCKET`, `STORAGE_S3_ENDPOINT`, and the key
pair in `.env` (see `backend/.env.example`), and run `reap-photo-uploads`
from your own cron with `maintenance_job_enabled = false`. The same CORS
requirement applies to whatever bucket you use.
