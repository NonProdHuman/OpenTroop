# Weekly maintenance job (GH-145 / GH-222).
#
# A Cloud Run Job running the backend image's reaper CLIs out-of-band:
#   - `reap-photo-uploads` — releases abandoned photo-upload quota reservations
#     and deletes soft-deleted photos' object bytes (GH-145, ADR 0011).
#   - `reap-tombstones`    — hard-deletes purged-member tombstones past the
#     retention window (GH-222, ADR 0010).
# Both are idempotent, so the weekly cadence only bounds how long garbage
# lingers, never correctness. Cloud Scheduler triggers the job on
# var.maintenance_schedule (default: Mondays 08:00 UTC).
#
# Ownership follows ADR 0009: Terraform owns the job *shell* (name, SA, env,
# schedule) and sets a bootstrap image only; GitHub Actions rolls the image on
# every deploy (deploy.yml, gated on GCP_MAINTENANCE_JOB_NAME).

resource "google_service_account" "maintenance" {
  count = local.maintenance_enabled ? 1 : 0

  account_id   = local.maintenance_sa_id
  display_name = "OpenTroop ${var.environment} maintenance job"

  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret_iam_member" "maintenance_secret_access" {
  for_each = local.maintenance_enabled ? toset(local.maintenance_secret_env_names) : []

  secret_id = google_secret_manager_secret.runtime[each.key].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.maintenance[0].email}"
}

resource "google_cloud_run_v2_job" "maintenance" {
  count = local.maintenance_enabled ? 1 : 0

  name                = local.maintenance_job_name
  location            = var.gcp_region
  deletion_protection = var.deletion_protection

  template {
    template {
      service_account = google_service_account.maintenance[0].email
      max_retries     = 1
      timeout         = "1800s"

      containers {
        image = var.api_image

        command = ["sh", "-c"]
        args    = ["uv run --no-dev reap-photo-uploads && uv run --no-dev reap-tombstones"]

        resources {
          limits = {
            cpu    = "1"
            memory = "512Mi"
          }
        }

        env {
          name  = "STORAGE_BACKEND"
          value = var.storage_backend
        }

        env {
          name  = "STORAGE_BUCKET"
          value = local.storage_bucket_name
        }

        env {
          name  = "STORAGE_S3_ENDPOINT"
          value = local.storage_s3_endpoint
        }

        env {
          name  = "ENVIRONMENT"
          value = var.environment
        }

        dynamic "env" {
          for_each = local.maintenance_secret_env_names

          content {
            name = env.value

            value_source {
              secret_key_ref {
                secret  = google_secret_manager_secret.runtime[env.value].secret_id
                version = "latest"
              }
            }
          }
        }
      }
    }
  }

  # GitHub Actions owns the running image; Terraform only bootstraps it (ADR 0009).
  lifecycle {
    ignore_changes = [template[0].template[0].containers[0].image]
  }

  depends_on = [
    google_project_service.required,
    google_secret_manager_secret_iam_member.maintenance_secret_access,
    google_secret_manager_secret_version.runtime,
  ]
}

# ── Scheduler trigger ─────────────────────────────────────────────────────────

resource "google_service_account" "scheduler" {
  count = local.maintenance_enabled ? 1 : 0

  account_id   = local.scheduler_sa_id
  display_name = "OpenTroop ${var.environment} Cloud Scheduler"

  depends_on = [google_project_service.required]
}

resource "google_cloud_run_v2_job_iam_member" "scheduler_invokes_maintenance" {
  count = local.maintenance_enabled ? 1 : 0

  name     = google_cloud_run_v2_job.maintenance[0].name
  location = var.gcp_region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler[0].email}"
}

resource "google_cloud_scheduler_job" "maintenance" {
  count = local.maintenance_enabled ? 1 : 0

  name      = "${local.maintenance_job_name}-weekly"
  region    = var.gcp_region
  schedule  = var.maintenance_schedule
  time_zone = var.maintenance_time_zone

  # A missed window (outage during the tick) is fine — the next weekly run
  # sweeps everything due; the reapers are cumulative and idempotent.
  attempt_deadline = "320s"

  retry_config {
    retry_count = 1
  }

  http_target {
    http_method = "POST"
    uri         = "https://run.googleapis.com/v2/projects/${var.gcp_project_id}/locations/${var.gcp_region}/jobs/${local.maintenance_job_name}:run"

    oauth_token {
      service_account_email = google_service_account.scheduler[0].email
    }
  }

  depends_on = [
    google_project_service.required,
    google_cloud_run_v2_job_iam_member.scheduler_invokes_maintenance,
  ]
}
