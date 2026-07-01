resource "random_password" "app_secret" {
  length  = 48
  special = true
}

resource "google_project_service" "required" {
  for_each = toset([
    "artifactregistry.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
  ])

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
        cpu_idle = true
      }

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
