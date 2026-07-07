# Nightly demo-edit reset job (GH-246, ADR 0012).
#
# A Cloud Run Job running `seed-dev-data --reset --slug <demo_edit_slug>` on a
# nightly Cloud Scheduler trigger. It wipes whatever visitors did in the private,
# Clerk-login demo-edit tenant back to the deterministic sample dataset — the
# "resets are fake" promise the demo banner makes. Idempotent (a re-seed of an
# existing slug tears down and re-creates), so a missed night just means the next
# run cleans up.
#
# Distinct from the anonymous *read-only* demo (that carve-out is enabled on the API
# service via DEMO_TENANT_SLUG and needs no scheduled job — nothing there mutates).
#
# Opt-in via var.demo_edit_reset_enabled (default false), so ordinary and self-host
# environments provision none of this. Ownership follows ADR 0009 exactly like the
# maintenance job: Terraform owns the job shell + schedule and bootstraps an image;
# GitHub Actions rolls the running image on deploy.
#
# NOTE: seed-dev-data writes through the app DB role (DATABASE_URL). Under FORCE RLS
# on a shared SaaS DB, point DATABASE_URL for this job at a BYPASSRLS role (or run it
# only on a demo environment). See ADR 0012.

resource "google_service_account" "demo_reset" {
  count = local.demo_reset_enabled ? 1 : 0

  account_id   = local.demo_reset_sa_id
  display_name = "OpenTroop ${var.environment} demo-edit reset job"

  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret_iam_member" "demo_reset_secret_access" {
  for_each = local.demo_reset_enabled ? toset(local.demo_reset_secret_env_names) : []

  secret_id = google_secret_manager_secret.runtime[each.key].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.demo_reset[0].email}"
}

resource "google_cloud_run_v2_job" "demo_reset" {
  count = local.demo_reset_enabled ? 1 : 0

  name                = local.demo_reset_job_name
  location            = var.gcp_region
  deletion_protection = var.deletion_protection

  template {
    template {
      service_account = google_service_account.demo_reset[0].email
      max_retries     = 1
      timeout         = "900s"

      containers {
        image = var.api_image

        command = ["sh", "-c"]
        args    = [local.demo_reset_command]

        resources {
          limits = {
            cpu    = "1"
            memory = "512Mi"
          }
        }

        env {
          name  = "ENVIRONMENT"
          value = var.environment
        }

        # seed-dev-data imports app.core.config at startup, which requires these.
        env {
          name  = "APP_DOMAIN"
          value = var.app_domain
        }

        env {
          name  = "CORS_ORIGINS"
          value = jsonencode(local.cors_origins)
        }

        dynamic "env" {
          for_each = local.demo_reset_secret_env_names

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
    google_secret_manager_secret_iam_member.demo_reset_secret_access,
    google_secret_manager_secret_version.runtime,
  ]
}

# ── Scheduler trigger ─────────────────────────────────────────────────────────

resource "google_service_account" "demo_reset_scheduler" {
  count = local.demo_reset_enabled ? 1 : 0

  account_id   = local.demo_reset_scheduler_sa_id
  display_name = "OpenTroop ${var.environment} demo-reset scheduler"

  depends_on = [google_project_service.required]
}

resource "google_cloud_run_v2_job_iam_member" "scheduler_invokes_demo_reset" {
  count = local.demo_reset_enabled ? 1 : 0

  name     = google_cloud_run_v2_job.demo_reset[0].name
  location = var.gcp_region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.demo_reset_scheduler[0].email}"
}

resource "google_cloud_scheduler_job" "demo_reset" {
  count = local.demo_reset_enabled ? 1 : 0

  name      = "${local.demo_reset_job_name}-nightly"
  region    = var.gcp_region
  schedule  = var.demo_edit_reset_schedule
  time_zone = var.demo_edit_reset_time_zone

  # A missed window is harmless — the reset is idempotent and the next night
  # sweeps everything back to the deterministic dataset.
  attempt_deadline = "320s"

  retry_config {
    retry_count = 1
  }

  http_target {
    http_method = "POST"
    uri         = "https://run.googleapis.com/v2/projects/${var.gcp_project_id}/locations/${var.gcp_region}/jobs/${local.demo_reset_job_name}:run"

    oauth_token {
      service_account_email = google_service_account.demo_reset_scheduler[0].email
    }
  }

  depends_on = [
    google_project_service.required,
    google_cloud_run_v2_job_iam_member.scheduler_invokes_demo_reset,
  ]
}
