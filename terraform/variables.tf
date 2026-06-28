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

variable "github_repository" {
  description = "GitHub repository allowed to deploy through Workload Identity Federation, in owner/name form."
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
  default     = "512Mi"
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
  default = {
    email = "{{user.primary_email_address}}"
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

variable "neon_min_cu" {
  description = "Minimum Neon compute units."
  type        = number
  default     = 0.25
}

variable "neon_max_cu" {
  description = "Maximum Neon compute units."
  type        = number
  default     = 1
}

variable "neon_suspend_timeout_seconds" {
  description = "Seconds before inactive Neon compute suspends."
  type        = number
  default     = 300
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
