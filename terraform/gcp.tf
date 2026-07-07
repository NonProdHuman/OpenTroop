resource "random_password" "app_secret" {
  length  = 48
  special = true
}

# X-Origin-Auth shared secret (GH-116). No special characters — it travels in an
# HTTP header and must survive any intermediary's header handling unmodified.
resource "random_password" "origin_secret" {
  length  = 48
  special = false
}

resource "google_project_service" "required" {
  for_each = toset(concat([
    "artifactregistry.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    ],
    local.cloudtasks_enabled ? ["cloudtasks.googleapis.com"] : [],
    local.maintenance_enabled ? ["cloudscheduler.googleapis.com"] : [],
  ))

  project            = var.gcp_project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_artifact_registry_repository" "containers" {
  location      = var.gcp_region
  repository_id = local.artifact_repository_name
  description   = "OpenTroop container images"
  format        = "DOCKER"

  depends_on = [google_project_service.required]

  # checkov:skip=CKV_GCP_84: This is a private Docker repository that will only be used by the Cloud Run service
}

resource "google_service_account" "api" {
  account_id   = local.api_service_account_id
  display_name = "OpenTroop ${var.environment} API runtime"

  depends_on = [google_project_service.required]
}

resource "google_service_account" "web" {
  account_id   = local.web_service_account_id
  display_name = "OpenTroop ${var.environment} Web runtime"

  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret" "runtime" {
  for_each = local.runtime_secret_names

  secret_id = "${local.name_prefix}-${lower(replace(each.key, "_", "-"))}"

  replication {
    auto {}
  }

  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret_version" "runtime" {
  for_each = local.runtime_secret_names

  secret      = google_secret_manager_secret.runtime[each.key].id
  secret_data = local.runtime_secret_values[each.key]
}

resource "google_secret_manager_secret_iam_member" "api_secret_access" {
  for_each = toset(local.api_secret_env_names)

  secret_id = google_secret_manager_secret.runtime[each.key].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.api.email}"
}

resource "google_secret_manager_secret_iam_member" "web_secret_access" {
  for_each = toset(local.web_secret_env_names)

  secret_id = google_secret_manager_secret.runtime[each.key].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.web.email}"
}

resource "google_cloud_run_v2_service" "api" {
  name                = local.api_service_name
  location            = var.gcp_region
  ingress             = var.api_ingress
  deletion_protection = var.deletion_protection

  template {
    service_account = google_service_account.api.email

    scaling {
      min_instance_count = var.api_min_instances
      max_instance_count = var.api_max_instances
    }

    containers {
      image = var.api_image

      ports {
        container_port = 8000
      }

      resources {
        limits = {
          cpu    = var.api_cpu
          memory = var.api_memory
        }
        # Request-based billing (cpu_idle = true) throttles CPU between requests,
        # which starves the in-process import drain loop — queued TWH imports
        # never run (GH-240). With the inprocess backend, keep CPU allocated for
        # the instance's lifetime; cloudtasks deployments keep the cheaper mode.
        cpu_idle = var.import_queue_backend != "inprocess"
      }

      env {
        name  = "APP_DOMAIN"
        value = var.app_domain
      }

      env {
        name  = "CORS_ORIGINS"
        value = jsonencode(local.cors_origins)
      }

      # The Cloudflare Worker overwrites X-Forwarded-Host on every proxied request, so
      # the backend may trust it for tenant resolution only when the Worker is in front.
      env {
        name  = "TRUST_FORWARDED_HOST"
        value = var.cloudflare_enabled ? "true" : "false"
      }

      # SaaS behind Cloudflare resolves tenants by subdomain only — the raw-UUID
      # X-Tenant-ID fallback would otherwise be a tenant existence-probing oracle
      # (GH-116). Kept enabled for direct/self-host deployments and local tooling.
      env {
        name  = "ALLOW_TENANT_ID_HEADER"
        value = var.cloudflare_enabled ? "false" : "true"
      }

      env {
        name  = "RATE_LIMIT_ENABLED"
        value = var.api_rate_limit_enabled ? "true" : "false"
      }

      env {
        name  = "CF_ACCESS_TEAM_DOMAIN"
        value = var.cf_access_enabled ? coalesce(var.cf_access_team_domain, "") : ""
      }

      env {
        name  = "CF_ACCESS_AUD"
        value = var.cf_access_enabled && var.cloudflare_enabled ? cloudflare_zero_trust_access_application.platform[0].aud : ""
      }

      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }

      env {
        name  = "EMAIL_BACKEND"
        value = var.email_backend
      }

      env {
        name  = "EMAIL_FROM_ADDRESS"
        value = coalesce(var.email_from_address, "")
      }

      # Object storage for event photos (GH-145, ADR 0011). Empty/none when the
      # feature is disabled; the access keys ride the secret env block below.
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

      # Async TWH import dispatch (GH-240). The queue/worker values are empty
      # unless import_queue_backend == "cloudtasks", in which case the API pushes
      # each job to the worker via Cloud Tasks; otherwise the backend drains
      # queued jobs in-process.
      env {
        name  = "IMPORT_QUEUE_BACKEND"
        value = var.import_queue_backend
      }
      # The inprocess backend only works if something drains the queue — that is
      # this lifespan loop. Without it POST /import/twh 202s and the job sits
      # queued forever. cloudtasks is push-driven; the loop stays off there.
      env {
        name  = "IMPORT_LOOP_ENABLED"
        value = var.import_queue_backend == "inprocess" ? "true" : "false"
      }
      env {
        name  = "CLOUDTASKS_QUEUE_PATH"
        value = local.import_tasks_queue_path
      }
      env {
        name  = "IMPORT_WORKER_URL"
        value = local.import_worker_url
      }
      env {
        name  = "IMPORT_WORKER_SERVICE_ACCOUNT"
        value = local.import_worker_service_account
      }

      dynamic "env" {
        for_each = local.api_secret_env_names

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

  # GitHub Actions owns the running image/revision; Terraform only bootstraps it
  # (ADR 0009). Ignoring image drift keeps `terraform apply` from reverting a deploy.
  lifecycle {
    ignore_changes = [template[0].containers[0].image]
  }

  depends_on = [
    google_project_service.required,
    google_secret_manager_secret_iam_member.api_secret_access,
    google_secret_manager_secret_version.runtime,
  ]
}

resource "google_cloud_run_v2_service" "web" {
  name                = local.web_service_name
  location            = var.gcp_region
  ingress             = var.web_ingress
  deletion_protection = var.deletion_protection

  template {
    service_account = google_service_account.web.email

    scaling {
      min_instance_count = var.web_min_instances
      max_instance_count = var.web_max_instances
    }

    containers {
      image = var.web_image

      ports {
        container_port = 3000
      }

      resources {
        limits = {
          cpu    = var.web_cpu
          memory = var.web_memory
        }
        cpu_idle = true
      }

      env {
        name  = "NEXT_PUBLIC_API_URL"
        value = local.api_public_url
      }

      env {
        name  = "NEXT_PUBLIC_APP_DOMAIN"
        value = var.app_domain
      }

      env {
        name  = "NEXT_PUBLIC_CLERK_JWT_TEMPLATE"
        value = var.manage_clerk_jwt_template ? var.clerk_jwt_template_name : ""
      }

      env {
        name  = "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY"
        value = var.clerk_publishable_key
      }

      dynamic "env" {
        for_each = local.web_secret_env_names

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

  # GitHub Actions owns the running image/revision; Terraform only bootstraps it
  # (ADR 0009). Ignoring image drift keeps `terraform apply` from reverting a deploy.
  lifecycle {
    ignore_changes = [template[0].containers[0].image]
  }

  depends_on = [
    google_project_service.required,
    google_secret_manager_secret_iam_member.web_secret_access,
    google_secret_manager_secret_version.runtime,
  ]
}

resource "google_cloud_run_v2_service_iam_member" "api_public" {
  location = google_cloud_run_v2_service.api.location
  name     = google_cloud_run_v2_service.api.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_v2_service_iam_member" "web_public" {
  location = google_cloud_run_v2_service.web.location
  name     = google_cloud_run_v2_service.web.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
