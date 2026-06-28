output "artifact_registry_repository" {
  description = "Artifact Registry repository for OpenTroop images."
  value       = "${var.gcp_region}-docker.pkg.dev/${var.gcp_project_id}/${google_artifact_registry_repository.containers.repository_id}"
}

output "artifact_registry_repository_name" {
  description = "Artifact Registry repository name."
  value       = google_artifact_registry_repository.containers.repository_id
}

output "api_service_name" {
  description = "Cloud Run backend service name."
  value       = google_cloud_run_v2_service.api.name
}

output "web_service_name" {
  description = "Cloud Run frontend service name."
  value       = google_cloud_run_v2_service.web.name
}

output "api_service_uri" {
  description = "Raw Cloud Run URL for the backend service."
  value       = google_cloud_run_v2_service.api.uri
}

output "web_service_uri" {
  description = "Raw Cloud Run URL for the frontend service."
  value       = google_cloud_run_v2_service.web.uri
}

output "api_public_url" {
  description = "Public API URL configured for the web app."
  value       = local.api_public_url
}

output "frontend_url" {
  description = "Primary frontend URL."
  value       = var.cloudflare_enabled ? "https://${var.app_domain}" : google_cloud_run_v2_service.web.uri
}

output "github_service_account" {
  description = "Service account GitHub Actions should impersonate."
  value       = google_service_account.github_deploy.email
}

output "github_workload_identity_provider" {
  description = "Workload Identity Provider resource name for google-github-actions/auth."
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "neon_project_id" {
  description = "Neon project ID when Terraform manages Neon."
  value       = var.manage_neon ? neon_project.database[0].id : null
}

output "database_url_secret_name" {
  description = "GCP Secret Manager secret holding DATABASE_URL."
  value       = google_secret_manager_secret.runtime["DATABASE_URL"].secret_id
}

output "cloudflare_record_names" {
  description = "Cloudflare record names managed for the environment."
  value = var.cloudflare_enabled ? {
    app      = local.cloudflare_app_record
    wildcard = local.cloudflare_wildcard_record
    api      = local.cloudflare_api_record
  } : null
}
