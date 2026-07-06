# Object storage for event photos (GH-145, ADR 0011).
#
# Cloudflare R2, spoken through the S3-compatible API. Terraform can own the
# bucket itself (manage_r2_bucket=true; needs an API token with R2 edit), or an
# existing bucket can be supplied via var.storage_bucket. Either way the bucket
# stays private — the backend mints short-lived presigned URLs for every access;
# there is no public-read configuration to manage here by design.
#
# The S3 access keys (an R2 API token's key pair) cannot be minted by the
# Cloudflare provider; create them in the dashboard and pass
# storage_access_key_id / storage_secret_access_key, which land in Secret
# Manager alongside the other runtime secrets.

resource "cloudflare_r2_bucket" "media" {
  count = var.cloudflare_enabled && var.manage_r2_bucket && var.storage_backend == "r2" ? 1 : 0

  account_id = var.cloudflare_account_id
  name       = local.storage_bucket_name
}

check "storage_configured" {
  assert {
    condition = !local.storage_enabled || (
      local.storage_bucket_name != "" && local.storage_s3_endpoint != ""
      && var.storage_access_key_id != null && var.storage_secret_access_key != null
    )
    error_message = "storage_backend is enabled but incomplete: bucket, endpoint (or cloudflare_account_id for r2), and both access keys are required."
  }
}
