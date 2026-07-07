variable "project_name" {
  description = "Short project name used in resource names."
  type        = string
  default     = "opentroop"
}

variable "environment" {
  description = "Environment name, such as staging, production, or pr-123."
  type        = string
  default     = "staging"
}

variable "gcp_project_id" {
  description = "Google Cloud project ID."
  type        = string
}

variable "gcp_region" {
  description = "Google Cloud region for Cloud Run and Artifact Registry."
  type        = string
  default     = "us-central1"
}

variable "app_domain" {
  description = "Primary application domain used for tenant subdomains."
  type        = string
}

variable "artifact_repository_name" {
  description = "Artifact Registry Docker repository name. Defaults to <project>-<environment>-containers."
  type        = string
  default     = null
}

variable "api_service_name" {
  description = "Cloud Run service name for the FastAPI backend. Defaults to <project>-<environment>-api."
  type        = string
  default     = null
}

variable "web_service_name" {
  description = "Cloud Run service name for the Next.js frontend. Defaults to <project>-<environment>-web."
  type        = string
  default     = null
}

variable "api_image" {
  description = "Initial backend container image to deploy. CI can update this after Terraform creates the service."
  type        = string
}

variable "web_image" {
  description = "Initial frontend container image to deploy. CI can update this after Terraform creates the service."
  type        = string
}

variable "api_cpu" {
  description = "CPU limit for the backend Cloud Run container."
  type        = string
  default     = "1"
}

variable "api_memory" {
  description = "Memory limit for the backend Cloud Run container."
  type        = string
  default     = "2Gi"
}

variable "web_cpu" {
  description = "CPU limit for the frontend Cloud Run container."
  type        = string
  default     = "1"
}

variable "web_memory" {
  description = "Memory limit for the frontend Cloud Run container."
  type        = string
  default     = "512Mi"
}

variable "api_min_instances" {
  description = "Minimum backend Cloud Run instances."
  type        = number
  default     = 0
}

variable "api_max_instances" {
  description = "Maximum backend Cloud Run instances."
  type        = number
  default     = 10
}

variable "web_min_instances" {
  description = "Minimum frontend Cloud Run instances."
  type        = number
  default     = 0
}

variable "web_max_instances" {
  description = "Maximum frontend Cloud Run instances."
  type        = number
  default     = 10
}

variable "cors_origins" {
  description = "Explicit CORS origins. Add raw Cloud Run preview URLs here when not using Cloudflare. Tenant subdomains are also covered by APP_DOMAIN-derived regex in the backend."
  type        = list(string)
  default     = []
}

variable "api_public_url" {
  description = "Public API URL baked into the web runtime. Defaults to https://api.<app_domain> when Cloudflare is enabled, otherwise the backend run.app URL."
  type        = string
  default     = null
}

variable "app_secret" {
  description = "HS256 secret used by the backend for invite/claim tokens. Generated when omitted."
  type        = string
  default     = null
  sensitive   = true
}

variable "auth_issuer" {
  description = "OIDC issuer URL. If omitted, clerk_frontend_api is used."
  type        = string
  default     = null
}

variable "auth_jwks_uri" {
  description = "OIDC JWKS URI. Defaults to <auth_issuer>/.well-known/jwks.json."
  type        = string
  default     = null
}

variable "auth_audience" {
  description = "OIDC audience. Leave null/empty for Clerk deployments without a configured audience."
  type        = string
  default     = null
}

variable "clerk_frontend_api" {
  description = "Clerk Frontend API host, for example capable-fox-42.clerk.accounts.dev."
  type        = string
  default     = null
}

variable "email_backend" {
  description = "Email delivery backend used by the API (\"fake\" or \"resend\"). See docs/resend-setup.md."
  type        = string
  default     = "fake"
}

variable "resend_api_key" {
  description = "Resend API key for email delivery. Required when email_backend = \"resend\"."
  type        = string
  default     = null
  sensitive   = true
}

variable "email_from_address" {
  description = "From address for outgoing email, e.g. noreply@opentroop.dev. Must be on a domain verified in Resend."
  type        = string
  default     = null
}

variable "clerk_publishable_key" {
  description = "Clerk publishable key exposed to the web app."
  type        = string
}

variable "clerk_secret_key" {
  description = "Clerk secret key used by server-side web code and optional JWT-template automation."
  type        = string
  sensitive   = true
}

variable "manage_clerk_jwt_template" {
  description = "Create or update a Clerk custom JWT template containing the email claim."
  type        = bool
  default     = false
}

variable "clerk_jwt_template_name" {
  description = "Clerk JWT template requested by the web app when manage_clerk_jwt_template is enabled."
  type        = string
  default     = "opentroop"
}

variable "clerk_jwt_claims" {
  description = "Claims JSON for the Clerk custom JWT template."
  type        = map(string)
  # email_verified must accompany email: the backend only honors email-based
  # account matching when the provider positively asserts verification.
  default = {
    email          = "{{user.primary_email_address}}"
    email_verified = "{{user.email_verified}}"
  }
}

variable "manage_neon" {
  description = "Provision a Neon project with the community kislerdm/neon provider."
  type        = bool
  default     = true
}

variable "neon_api_key" {
  description = "Neon API key. May also be provided through NEON_API_KEY."
  type        = string
  default     = null
  sensitive   = true
}

variable "neon_region_id" {
  description = "Neon region ID, for example aws-us-east-1."
  type        = string
  default     = "aws-us-east-1"
}

variable "neon_pg_version" {
  description = "Postgres major version for Neon."
  type        = number
  default     = 16
}

variable "neon_branch_name" {
  description = "Default Neon branch name."
  type        = string
  default     = "main"
}

variable "neon_database_name" {
  description = "Default Neon database name."
  type        = string
  default     = "opentroop"
}

variable "neon_owner_role" {
  description = "Default Neon owner role."
  type        = string
  default     = "opentroop_owner"
}

variable "neon_app_role" {
  description = "Neon login role for tenant-scoped application traffic."
  type        = string
  default     = "opentroop_app"
}

# variable "neon_min_cu" {
#   description = "Minimum Neon compute units."
#   type        = number
#   default     = 0.25
# }

# variable "neon_max_cu" {
#   description = "Maximum Neon compute units."
#   type        = number
#   default     = 1
# }

# variable "neon_suspend_timeout_seconds" {
#   description = "Seconds before inactive Neon compute suspends."
#   type        = number
#   default     = 300
# }

variable "neon_history_retention_seconds" {
  description = "History retention in seconds for the Neon project (maximum of 21600 / 6 hours for Free tier, default 86400 / 24 hours for paid plans)."
  type        = number
  default     = 21600
}

variable "database_url" {
  description = "Override DATABASE_URL. Defaults to the Neon app-role URL when manage_neon is true."
  type        = string
  default     = null
  sensitive   = true
}

variable "database_url_admin" {
  description = "Override DATABASE_URL_ADMIN. Defaults to the Neon owner URL when manage_neon is true."
  type        = string
  default     = null
  sensitive   = true
}

variable "database_url_migrate" {
  description = "Override DATABASE_URL_MIGRATE. Defaults to the Neon owner URL when manage_neon is true."
  type        = string
  default     = null
  sensitive   = true
}

variable "cloudflare_enabled" {
  description = "Manage Cloudflare DNS records and Worker proxy."
  type        = bool
  default     = true
}

variable "cloudflare_api_token" {
  description = "Cloudflare API token with DNS and Workers permissions."
  type        = string
  default     = null
  sensitive   = true
}

variable "cloudflare_zone_id" {
  description = "Cloudflare zone ID that contains app_domain."
  type        = string
  default     = null
}

variable "cloudflare_account_id" {
  description = "Cloudflare account ID used for Workers."
  type        = string
  default     = null
}

variable "cloudflare_zone_name" {
  description = "Cloudflare zone name that contains app_domain. Defaults to app_domain, which is correct for production apex deployments."
  type        = string
  default     = null
}

variable "cloudflare_apex_record_name" {
  description = "Override the Cloudflare record name for app_domain. Defaults to @ for zone apex or the subdomain prefix for nested environments."
  type        = string
  default     = null
}

variable "cloudflare_wildcard_record_name" {
  description = "Override the Cloudflare wildcard record name. Defaults to * for zone apex or *.<subdomain-prefix> for nested environments."
  type        = string
  default     = null
}

variable "cloudflare_api_record_name" {
  description = "Override the Cloudflare API record name. Defaults to api for zone apex or api.<subdomain-prefix> for nested environments."
  type        = string
  default     = null
}

variable "origin_shared_secret" {
  description = "Shared secret the Cloudflare Worker injects as X-Origin-Auth so the API can reject direct *.run.app traffic (GH-116). Generated when omitted."
  type        = string
  default     = null
  sensitive   = true
}

variable "api_rate_limit_enabled" {
  description = "Enable the API's in-process per-tenant/per-IP rate limiting (RATE_LIMIT_ENABLED). App-layer backstop behind the Cloudflare rules."
  type        = bool
  default     = true
}

variable "cloudflare_waf_enabled" {
  description = "Deploy the Cloudflare Managed + OWASP Core WAF rulesets on the zone (GH-116). Requires a Cloudflare Pro plan or higher."
  type        = bool
  default     = false
}

variable "cloudflare_rate_limit_enabled" {
  description = "Deploy Cloudflare rate-limiting rules for the calendar-feed and auth hot paths (GH-116). Plan limits apply — the Free plan allows one rate-limiting rule with a 10s period; the values used here assume Pro or higher."
  type        = bool
  default     = false
}

variable "cf_access_enabled" {
  description = "Put the platform control plane (admin subdomain + /platform API paths) behind a Cloudflare Access application (GH-117). Requires a Zero Trust team on the account."
  type        = bool
  default     = false
}

variable "cf_access_team_domain" {
  description = "Cloudflare Zero Trust team domain prefix (e.g. \"myteam\" for myteam.cloudflareaccess.com). Required when cf_access_enabled."
  type        = string
  default     = null
}

variable "cf_access_allowed_emails" {
  description = "Staff email addresses allowed through the platform Cloudflare Access policy. Required when cf_access_enabled."
  type        = list(string)
  default     = []
}

variable "api_ingress" {
  description = "Ingress traffic policy for the API service. Can be INGRESS_TRAFFIC_ALL, INGRESS_TRAFFIC_INTERNAL_ONLY, or INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER."
  type        = string
  default     = "INGRESS_TRAFFIC_ALL"
}

variable "web_ingress" {
  description = "Ingress traffic policy for the Web service. Can be INGRESS_TRAFFIC_ALL, INGRESS_TRAFFIC_INTERNAL_ONLY, or INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER."
  type        = string
  default     = "INGRESS_TRAFFIC_ALL"
}

variable "deletion_protection" {
  description = "Enable or disable deletion protection on Cloud Run services."
  type        = bool
  default     = false
}

# ── Async TWH import worker (GH-240) ──────────────────────────────────────────

variable "import_queue_backend" {
  description = "How queued TWH imports are dispatched. 'inprocess' (default; self-host/dev — the API drains jobs in a background loop / CLI) or 'cloudtasks' (SaaS — provisions a Cloud Tasks queue + dedicated worker Cloud Run service). Must match the API's IMPORT_QUEUE_BACKEND env."
  type        = string
  default     = "inprocess"

  validation {
    condition     = contains(["inprocess", "cloudtasks"], var.import_queue_backend)
    error_message = "import_queue_backend must be 'inprocess' or 'cloudtasks'."
  }
}

variable "import_worker_url" {
  description = "Override for the import worker's URL (the Cloud Tasks OIDC audience). Leave empty to use Cloud Run's deterministic URL; set it to the service's actual URI only if the postcondition reports a mismatch (older projects use a hashed URL)."
  type        = string
  default     = ""
}

variable "import_worker_ingress" {
  description = "Ingress policy for the import worker service. Only Cloud Tasks (as the worker SA) may invoke it — there is no public invoker binding."
  type        = string
  default     = "INGRESS_TRAFFIC_ALL"
}

variable "import_worker_timeout_seconds" {
  description = "Request timeout for the import worker (a single import runs inside one Cloud Tasks push). Cloud Run's max is 3600."
  type        = number
  default     = 3600
}

variable "import_worker_cpu" {
  description = "CPU limit for the import worker service."
  type        = string
  default     = "1"
}

variable "import_worker_memory" {
  description = "Memory limit for the import worker service (imports stream-parse but stage rows; give it headroom)."
  type        = string
  default     = "2Gi"
}

variable "import_worker_max_instances" {
  description = "Max instances for the import worker (also the Cloud Tasks max concurrent dispatches). Imports are serialized per tenant; a small ceiling is plenty."
  type        = number
  default     = 3
}

# ── Object storage for event photos (GH-145, ADR 0011) ────────────────────────

variable "storage_backend" {
  description = "Object storage driver for event photos. 'none' disables the feature; 'r2' (Cloudflare R2, the ADR 0011 SaaS default), 's3', and 'gcs' all speak the S3-compatible API. Must match the backend's STORAGE_BACKEND env."
  type        = string
  default     = "none"

  validation {
    condition     = contains(["none", "r2", "s3", "gcs"], var.storage_backend)
    error_message = "storage_backend must be one of 'none', 'r2', 's3', or 'gcs'."
  }
}

variable "manage_r2_bucket" {
  description = "Create the R2 bucket via the Cloudflare provider (requires an API token with R2 edit permission). Off by default so existing buckets can be supplied via storage_bucket without import."
  type        = bool
  default     = false
}

variable "manage_r2_cors" {
  description = "Manage the R2 bucket CORS policy via the Cloudflare provider (requires an API token with R2 edit permission — the same one manage_r2_bucket needs). Origins are derived from cors_origins (app_domain-based) so each environment gets correct browser-upload origins automatically. Set false to manage CORS by hand in the dashboard (e.g. bring-your-own-bucket with a low-privilege provider token)."
  type        = bool
  default     = true
}

variable "storage_bucket" {
  description = "Object storage bucket for event photos. Defaults to '<name_prefix>-media' when storage is enabled."
  type        = string
  default     = null
}

variable "storage_s3_endpoint" {
  description = "S3-compatible endpoint URL. For R2 this defaults to https://<cloudflare_account_id>.r2.cloudflarestorage.com; AWS S3 leaves it empty."
  type        = string
  default     = null
}

variable "storage_access_key_id" {
  description = "S3-compatible access key id (for R2: an R2 API token's access key). Stored in Secret Manager."
  type        = string
  default     = null
  sensitive   = true
}

variable "storage_secret_access_key" {
  description = "S3-compatible secret access key. Stored in Secret Manager."
  type        = string
  default     = null
  sensitive   = true
}

# ── Weekly maintenance job (reapers) ──────────────────────────────────────────

variable "maintenance_job_enabled" {
  description = "Provision the Cloud Run maintenance job + weekly Cloud Scheduler trigger that runs `reap-photo-uploads` and `reap-tombstones` (GH-145/GH-222). Disable for self-host setups that run the CLIs from their own cron."
  type        = bool
  default     = true
}

variable "maintenance_job_name" {
  description = "Override the Cloud Run maintenance job name. Defaults to '<name_prefix>-maintenance'."
  type        = string
  default     = null
}

variable "maintenance_schedule" {
  description = "Cron schedule for the maintenance job. Default: weekly, Mondays 08:00 UTC (Sunday night US — after weekend-campout uploads settle)."
  type        = string
  default     = "0 8 * * 1"
}

variable "maintenance_time_zone" {
  description = "IANA time zone the maintenance_schedule is evaluated in."
  type        = string
  default     = "Etc/UTC"
}
