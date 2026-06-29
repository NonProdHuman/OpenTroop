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

  clerk_issuer = var.clerk_frontend_api == null ? null : "https://${var.clerk_frontend_api}"
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

  api_public_url = try(coalesce(
    var.api_public_url,
    var.cloudflare_enabled ? "https://api.${var.app_domain}" : google_cloud_run_v2_service.api.uri,
  ), null)

  cors_origins = distinct(concat(
    var.cors_origins,
    [
      "https://${var.app_domain}",
    ],
  ))

  runtime_secret_values = {
    for k, v in {
      APP_SECRET           = local.app_secret
      AUTH_AUDIENCE        = var.auth_audience
      AUTH_ISSUER          = local.auth_issuer
      AUTH_JWKS_URI        = local.auth_jwks_uri
      CLERK_SECRET_KEY     = var.clerk_secret_key
      DATABASE_URL         = local.database_url
      DATABASE_URL_ADMIN   = local.database_url_admin
      DATABASE_URL_MIGRATE = local.database_url_migrate
    } : k => v if v != null
  }

  runtime_secret_names = nonsensitive(toset(keys(local.runtime_secret_values)))

  api_secret_env_names = nonsensitive([
    for name in [
      "APP_SECRET",
      "AUTH_AUDIENCE",
      "AUTH_ISSUER",
      "AUTH_JWKS_URI",
      "DATABASE_URL",
      "DATABASE_URL_ADMIN",
      "DATABASE_URL_MIGRATE",
    ] : name if lookup(local.runtime_secret_values, name, null) != null
  ])

  web_secret_env_names = nonsensitive([
    for name in [
      "CLERK_SECRET_KEY",
    ] : name if lookup(local.runtime_secret_values, name, null) != null
  ])

  api_service_account_id    = "${substr(local.name_prefix, 0, 20)}-api"
  web_service_account_id    = "${substr(local.name_prefix, 0, 20)}-web"
  github_service_account_id = "${substr(local.name_prefix, 0, 20)}-github"
  workload_identity_pool_id = "${substr(local.name_prefix, 0, 24)}-github"
  worker_name               = "${local.name_prefix}-proxy"
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
