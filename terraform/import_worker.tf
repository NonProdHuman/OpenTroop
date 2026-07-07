# Async TWH import worker (GH-240).
#
# When var.import_queue_backend == "cloudtasks", POST /import/twh persists the job
# and pushes it to a Cloud Tasks queue, which POSTs each job (with a Google OIDC
# token) to a dedicated worker Cloud Run service running the same image with a long
# request timeout. This decouples the (potentially multi-minute) import from the
# user's HTTP request. Everything here is gated on that backend; self-host and dev
# run imports in-process and none of these resources are created.

data "google_project" "this" {
  project_id = var.gcp_project_id
}

# ── Cloud Tasks queue ─────────────────────────────────────────────────────────

resource "google_cloud_tasks_queue" "imports" {
  count = local.cloudtasks_enabled ? 1 : 0

  name     = local.import_tasks_queue_name
  location = var.gcp_region
  project  = var.gcp_project_id

  # One import runs at a time (the backend also enforces one active import per
  # tenant); Cloud Tasks owns retry/backoff so a transient failure re-drives.
  rate_limits {
    max_dispatches_per_second = 1
    max_concurrent_dispatches = var.import_worker_max_instances
  }

  retry_config {
    max_attempts       = 5
    min_backoff        = "10s"
    max_backoff        = "300s"
    max_doublings      = 4
    max_retry_duration = "3600s"
  }

  depends_on = [google_project_service.required]
}

# ── Worker service account (worker runtime + Cloud Tasks OIDC identity) ────────

resource "google_service_account" "import_worker" {
  count = local.cloudtasks_enabled ? 1 : 0

  account_id   = local.import_worker_sa_id
  display_name = "OpenTroop ${var.environment} import worker"

  depends_on = [google_project_service.required]
}

# The worker reads the same runtime secrets as the API (DB, APP_SECRET, …), minus
# the origin secret which it must not require.
resource "google_secret_manager_secret_iam_member" "import_worker_secret_access" {
  for_each = local.cloudtasks_enabled ? toset(local.import_worker_secret_env_names) : []

  secret_id = google_secret_manager_secret.runtime[each.key].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.import_worker[0].email}"
}

# ── Worker Cloud Run service ──────────────────────────────────────────────────

resource "google_cloud_run_v2_service" "import_worker" {
  count = local.cloudtasks_enabled ? 1 : 0

  name                = local.import_worker_service_name
  location            = var.gcp_region
  ingress             = var.import_worker_ingress
  deletion_protection = var.deletion_protection

  template {
    service_account = google_service_account.import_worker[0].email
    # Imports can run for minutes; Cloud Tasks holds the push connection open.
    timeout = "${var.import_worker_timeout_seconds}s"

    scaling {
      # Scale to zero between imports; scale up only while jobs run.
      min_instance_count = 0
      max_instance_count = var.import_worker_max_instances
    }

    containers {
      image = var.api_image

      ports {
        container_port = 8000
      }

      resources {
        limits = {
          cpu    = var.import_worker_cpu
          memory = var.import_worker_memory
        }
        # CPU is allocated for the whole request, which is the entire import — no
        # "CPU always allocated" needed because the work happens inside the push.
        cpu_idle = true
      }

      # Direct Cloud Tasks traffic: no Cloudflare Worker in front, so no
      # X-Origin-Auth (ORIGIN_SHARED_SECRET intentionally absent) and no
      # per-tenant rate limiting. Auth is the Google OIDC token the worker
      # endpoint verifies (app/core/import_worker_auth.py) + Cloud Run IAM.
      env {
        name  = "APP_DOMAIN"
        value = var.app_domain
      }
      env {
        name  = "CORS_ORIGINS"
        value = jsonencode(local.cors_origins)
      }
      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }
      env {
        name  = "RATE_LIMIT_ENABLED"
        value = "false"
      }
      env {
        name  = "TRUST_FORWARDED_HOST"
        value = "false"
      }
      # Push-driven, not loop-driven — never run the in-process drain here.
      env {
        name  = "IMPORT_LOOP_ENABLED"
        value = "false"
      }
      env {
        name  = "IMPORT_QUEUE_BACKEND"
        value = "cloudtasks"
      }
      # The worker verifies the OIDC token's audience == its own URL and email ==
      # its service account.
      env {
        name  = "IMPORT_WORKER_URL"
        value = local.import_worker_url
      }
      env {
        name  = "IMPORT_WORKER_SERVICE_ACCOUNT"
        value = google_service_account.import_worker[0].email
      }

      dynamic "env" {
        for_each = toset(local.import_worker_secret_env_names)

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

  # GitHub Actions owns the running image/revision (ADR 0009); Terraform bootstraps
  # it. The postcondition catches a Cloud Run URL that doesn't match the computed
  # deterministic form (older projects use a hashed URL) — set var.import_worker_url
  # to the printed service URI and re-apply.
  lifecycle {
    ignore_changes = [template[0].containers[0].image]

    postcondition {
      condition     = self.uri == local.import_worker_url
      error_message = "import_worker_url (${local.import_worker_url}) does not match the created service URI (${self.uri}). Set var.import_worker_url to that URI and re-apply."
    }
  }

  depends_on = [
    google_project_service.required,
    google_secret_manager_secret_iam_member.import_worker_secret_access,
    google_secret_manager_secret_version.runtime,
  ]
}

# ── IAM wiring ────────────────────────────────────────────────────────────────

# Cloud Tasks invokes the worker as the worker SA (OIDC) — grant it run.invoker.
# No allUsers invoker: the worker is not publicly callable.
resource "google_cloud_run_v2_service_iam_member" "import_worker_invoker" {
  count = local.cloudtasks_enabled ? 1 : 0

  location = google_cloud_run_v2_service.import_worker[0].location
  name     = google_cloud_run_v2_service.import_worker[0].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.import_worker[0].email}"
}

# The API service enqueues tasks — grant its SA enqueuer on the queue.
resource "google_cloud_tasks_queue_iam_member" "api_enqueuer" {
  count = local.cloudtasks_enabled ? 1 : 0

  name     = google_cloud_tasks_queue.imports[0].name
  location = google_cloud_tasks_queue.imports[0].location
  project  = var.gcp_project_id
  role     = "roles/cloudtasks.enqueuer"
  member   = "serviceAccount:${google_service_account.api.email}"
}

# Setting the worker SA as a task's OIDC identity requires the API SA to actAs it.
resource "google_service_account_iam_member" "api_acts_as_import_worker" {
  count = local.cloudtasks_enabled ? 1 : 0

  service_account_id = google_service_account.import_worker[0].name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.api.email}"
}

# ── Outputs (operator reference / GitHub Actions vars) ────────────────────────

output "import_worker_service_name" {
  description = "Cloud Run service name of the import worker (set as GCP_IMPORT_WORKER_SERVICE_NAME so the deploy workflow rolls it)."
  value       = local.cloudtasks_enabled ? google_cloud_run_v2_service.import_worker[0].name : null
}

output "import_worker_uri" {
  description = "Actual URI of the import worker service (should equal the computed import_worker_url)."
  value       = local.cloudtasks_enabled ? google_cloud_run_v2_service.import_worker[0].uri : null
}

output "import_tasks_queue_path" {
  description = "Cloud Tasks queue resource path used by the API (CLOUDTASKS_QUEUE_PATH)."
  value       = local.import_tasks_queue_path
}
