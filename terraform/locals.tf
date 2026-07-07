locals {
  raw_name_prefix = lower("${var.project_name}-${var.environment}")
  name_prefix     = substr(replace(replace(local.raw_name_prefix, "_", "-"), ".", "-"), 0, 40)

  artifact_repository_name = coalesce(var.artifact_repository_name, "${local.name_prefix}-containers")
  api_service_name         = coalesce(var.api_service_name, "${local.name_prefix}-api")
  web_service_name         = coalesce(var.web_service_name, "${local.name_prefix}-web")

  cloudflare_zone_name     = coalesce(var.cloudflare_zone_name, var.app_domain)
  cloudflare_app_subdomain = var.app_domain == local.cloudflare_zone_name ? null : trimsuffix(var.app_domain, ".${local.cloudflare_zone_name}")
  cloudflare_app_record    = coalesce(var.cloudflare_apex_record_name, local.cloudflare_app_subdomain == null ? "@" : local.cloudflare_app_subdomain)
  cloudflare_wildcard_record = coalesce(
    var.cloudflare_wildcard_record_name,
    local.cloudflare_app_subdomain == null ? "*" : "*.${local.cloudflare_app_subdomain}",
  )
  cloudflare_api_record = coalesce(
    var.cloudflare_api_record_name,
    local.cloudflare_app_subdomain == null ? "api" : "api.${local.cloudflare_app_subdomain}",
  )

  clerk_issuer = var.clerk_frontend_api == null ? null : "https://${replace(var.clerk_frontend_api, "https://", "")}"
  auth_issuer  = try(coalesce(var.auth_issuer, local.clerk_issuer), null)
  auth_jwks_uri = try(
    coalesce(var.auth_jwks_uri, local.auth_issuer == null ? null : "${local.auth_issuer}/.well-known/jwks.json"),
    null,
  )

  neon_owner_database_url = var.manage_neon ? replace(
    neon_project.database[0].connection_uri,
    "postgresql://",
    "postgresql+psycopg://",
  ) : null

  neon_app_database_url = var.manage_neon ? format(
    "postgresql+psycopg://%s:%s@%s/%s?sslmode=require",
    neon_role.app[0].name,
    urlencode(neon_role.app[0].password),
    neon_project.database[0].database_host,
    neon_project.database[0].database_name,
  ) : null

  database_url         = try(coalesce(var.database_url, local.neon_app_database_url), null)
  database_url_admin   = try(coalesce(var.database_url_admin, local.neon_owner_database_url, local.database_url), null)
  database_url_migrate = try(coalesce(var.database_url_migrate, local.neon_owner_database_url, local.database_url), null)

  app_secret = try(coalesce(var.app_secret, random_password.app_secret.result), null)

  # X-Origin-Auth shared secret (GH-116): the Worker injects it, the API requires it.
  # Only provisioned when Cloudflare fronts the deployment — with no trusted proxy
  # there is nothing to authenticate and the backend check stays disabled.
  origin_shared_secret = try(coalesce(var.origin_shared_secret, random_password.origin_secret.result), null)

  api_public_url = try(coalesce(
    var.api_public_url,
    var.cloudflare_enabled ? "https://api.${var.app_domain}" : google_cloud_run_v2_service.api.uri,
  ), null)

  cors_origins = distinct(concat(
    var.cors_origins,
    [
      "https://${var.app_domain}",
      "https://*.${var.app_domain}",
    ],
  ))

  runtime_secret_values = {
    APP_SECRET                = local.app_secret
    AUTH_AUDIENCE             = var.auth_audience
    AUTH_ISSUER               = local.auth_issuer
    AUTH_JWKS_URI             = local.auth_jwks_uri
    CLERK_SECRET_KEY          = var.clerk_secret_key
    DATABASE_URL              = local.database_url
    DATABASE_URL_ADMIN        = local.database_url_admin
    DATABASE_URL_MIGRATE      = local.database_url_migrate
    ORIGIN_SHARED_SECRET      = local.origin_shared_secret
    RESEND_API_KEY            = var.resend_api_key
    STORAGE_ACCESS_KEY_ID     = var.storage_access_key_id
    STORAGE_SECRET_ACCESS_KEY = var.storage_secret_access_key
  }

  runtime_secret_names = nonsensitive(toset(concat(
    ["APP_SECRET"],
    var.auth_audience != null ? ["AUTH_AUDIENCE"] : [],
    var.auth_issuer != null || var.clerk_frontend_api != null ? ["AUTH_ISSUER"] : [],
    var.auth_jwks_uri != null || var.auth_issuer != null || var.clerk_frontend_api != null ? ["AUTH_JWKS_URI"] : [],
    var.clerk_secret_key != null ? ["CLERK_SECRET_KEY"] : [],
    var.database_url != null || var.manage_neon ? ["DATABASE_URL"] : [],
    var.database_url_admin != null || var.manage_neon || var.database_url != null ? ["DATABASE_URL_ADMIN"] : [],
    var.database_url_migrate != null || var.manage_neon || var.database_url != null ? ["DATABASE_URL_MIGRATE"] : [],
    var.cloudflare_enabled ? ["ORIGIN_SHARED_SECRET"] : [],
    var.resend_api_key != null ? ["RESEND_API_KEY"] : [],
    var.storage_access_key_id != null ? ["STORAGE_ACCESS_KEY_ID"] : [],
    var.storage_secret_access_key != null ? ["STORAGE_SECRET_ACCESS_KEY"] : [],
  )))

  api_secret_env_names = nonsensitive(compact([
    "APP_SECRET",
    var.auth_audience != null ? "AUTH_AUDIENCE" : "",
    var.auth_issuer != null || var.clerk_frontend_api != null ? "AUTH_ISSUER" : "",
    var.auth_jwks_uri != null || var.auth_issuer != null || var.clerk_frontend_api != null ? "AUTH_JWKS_URI" : "",
    var.database_url != null || var.manage_neon ? "DATABASE_URL" : "",
    var.database_url_admin != null || var.manage_neon || var.database_url != null ? "DATABASE_URL_ADMIN" : "",
    var.database_url_migrate != null || var.manage_neon || var.database_url != null ? "DATABASE_URL_MIGRATE" : "",
    var.cloudflare_enabled ? "ORIGIN_SHARED_SECRET" : "",
    var.resend_api_key != null ? "RESEND_API_KEY" : "",
    var.storage_access_key_id != null ? "STORAGE_ACCESS_KEY_ID" : "",
    var.storage_secret_access_key != null ? "STORAGE_SECRET_ACCESS_KEY" : "",
  ]))

  web_secret_env_names = nonsensitive(compact([
    var.clerk_secret_key != null ? "CLERK_SECRET_KEY" : "",
  ]))

  api_service_account_id = "${substr(local.name_prefix, 0, 20)}-api"
  web_service_account_id = "${substr(local.name_prefix, 0, 20)}-web"
  worker_name            = "${local.name_prefix}-proxy"

  # Object storage for event photos (GH-145, ADR 0011). The bucket name and the
  # R2 endpoint derive from the environment; both flow to the API service and the
  # maintenance job as plain env (the keys are Secret Manager secrets).
  storage_enabled     = var.storage_backend != "none"
  storage_bucket_name = local.storage_enabled ? coalesce(var.storage_bucket, "${local.name_prefix}-media") : ""
  storage_s3_endpoint = local.storage_enabled ? coalesce(
    var.storage_s3_endpoint,
    var.storage_backend == "r2" && var.cloudflare_account_id != null ? "https://${var.cloudflare_account_id}.r2.cloudflarestorage.com" : "",
  ) : ""

  # Weekly maintenance job (reap-photo-uploads + reap-tombstones). Terraform owns
  # the job shell; GitHub Actions rolls its image on deploy (ADR 0009).
  maintenance_enabled  = var.maintenance_job_enabled
  maintenance_job_name = coalesce(var.maintenance_job_name, "${local.name_prefix}-maintenance")
  maintenance_sa_id    = "${substr(local.name_prefix, 0, 20)}-mnt"
  scheduler_sa_id      = "${substr(local.name_prefix, 0, 20)}-sch"

  # The job never serves HTTP, so it has no use for the origin secret.
  maintenance_secret_env_names = [for n in local.api_secret_env_names : n if n != "ORIGIN_SHARED_SECRET"]

  # Nightly demo-edit reset job (GH-246, ADR 0012). Same ownership model as the
  # maintenance job: Terraform owns the shell, GitHub Actions rolls the image.
  # Reuses the maintenance secret set (DB creds + APP_SECRET; no origin secret).
  demo_reset_enabled          = var.demo_edit_reset_enabled
  demo_reset_job_name         = "${local.name_prefix}-demo-reset"
  demo_reset_sa_id            = "${substr(local.name_prefix, 0, 20)}-dmr"
  demo_reset_scheduler_sa_id  = "${substr(local.name_prefix, 0, 20)}-dms"
  demo_reset_secret_env_names = local.maintenance_secret_env_names
  demo_reset_email_flag       = var.demo_edit_admin_email != null ? " --email ${var.demo_edit_admin_email}" : ""
  demo_reset_command          = "uv run --no-dev seed-dev-data --reset --slug ${var.demo_edit_slug}${local.demo_reset_email_flag}"

  # Async TWH import worker (GH-240). Provisioned only when the SaaS Cloud Tasks
  # backend is selected; self-host/dev use the in-process drain loop and none of
  # the resources below exist.
  cloudtasks_enabled            = var.import_queue_backend == "cloudtasks"
  import_worker_service_name    = "${local.name_prefix}-import-worker"
  import_worker_sa_id           = "${substr(local.name_prefix, 0, 20)}-imp"
  import_tasks_queue_name       = "${local.name_prefix}-imports"
  import_worker_service_account = local.cloudtasks_enabled ? google_service_account.import_worker[0].email : ""

  # Cloud Run's deterministic URL for the worker. Computed (not the resource's own
  # .uri) so the worker can carry its own URL as the OIDC audience without a
  # self-reference cycle; a postcondition on the service verifies it matches.
  import_worker_url = local.cloudtasks_enabled ? coalesce(
    var.import_worker_url,
    "https://${local.import_worker_service_name}-${data.google_project.this.number}.${var.gcp_region}.run.app",
  ) : ""
  import_tasks_queue_path = local.cloudtasks_enabled ? google_cloud_tasks_queue.imports[0].id : ""

  # The worker takes direct Cloud Tasks traffic (not via the Cloudflare Worker), so
  # it must NOT require X-Origin-Auth — otherwise OriginAuthMiddleware 403s
  # /import/jobs/execute. Its secret env is the API's minus ORIGIN_SHARED_SECRET.
  import_worker_secret_env_names = [for n in local.api_secret_env_names : n if n != "ORIGIN_SHARED_SECRET"]
}

check "database_url_configured" {
  assert {
    condition     = local.database_url != null && local.database_url != ""
    error_message = "DATABASE_URL is not configured. Set manage_neon=true with neon_api_key or provide database_url."
  }
}

check "database_url_admin_not_app_role" {
  assert {
    condition     = local.database_url_admin == null || local.database_url == null || local.database_url_admin != local.database_url
    error_message = "DATABASE_URL_ADMIN falls back to the application-level DATABASE_URL. An administrative database role is required to manage migrations and admin features."
  }
}

check "auth_configured" {
  assert {
    condition     = local.auth_issuer != null && local.auth_issuer != "" && local.auth_jwks_uri != null && local.auth_jwks_uri != ""
    error_message = "Auth is not configured. Provide auth_issuer/auth_jwks_uri or clerk_frontend_api."
  }
}

check "cloudflare_app_domain_in_zone" {
  assert {
    condition = (
      !var.cloudflare_enabled
      || var.app_domain == local.cloudflare_zone_name
      || endswith(var.app_domain, ".${local.cloudflare_zone_name}")
    )
    error_message = "app_domain must be the Cloudflare zone name or a subdomain of cloudflare_zone_name."
  }
}
