# Edge defense for the shared SaaS origin (GH-116) and the platform control
# plane (GH-117). Everything here is opt-in via variables because the WAF
# managed rulesets and multi-rule rate limiting need a Cloudflare Pro plan, and
# Access needs a Zero Trust team on the account. The origin shared secret (see
# cloudflare.tf worker bindings + gcp.tf env) has no plan requirement and is
# always on when Cloudflare fronts the deployment.

# --- Managed WAF (Cloudflare Managed Ruleset + OWASP Core) -------------------
# Ruleset IDs are Cloudflare's published, account-independent managed ruleset ids.
# Recommended rollout: deploy, watch Security > Events for false positives on the
# tenant subdomains for a few days, then tighten the OWASP paranoia/score if quiet.

resource "cloudflare_ruleset" "waf_managed" {
  count = var.cloudflare_enabled && var.cloudflare_waf_enabled ? 1 : 0

  zone_id = var.cloudflare_zone_id
  name    = "${local.name_prefix} managed WAF"
  kind    = "zone"
  phase   = "http_request_firewall_managed"

  rules = [
    {
      ref         = "cloudflare_managed"
      description = "Cloudflare Managed Ruleset"
      expression  = "true"
      action      = "execute"
      action_parameters = {
        id = "efb7b8c949ac4650a09736fc376e9aee"
      }
    },
    {
      ref         = "owasp_core"
      description = "Cloudflare OWASP Core Ruleset"
      expression  = "true"
      action      = "execute"
      action_parameters = {
        id = "4814384a9e5d4991b9815dcfc25d2f1f"
      }
    }
  ]
}

# --- Rate limiting for the hot/abusable paths --------------------------------
# The API is reachable both at api.<domain>/... and <any-host>/api/... (the Worker
# strips the /api prefix), so each rule matches both shapes. These are per-IP edge
# limits; the app-layer per-tenant limiter (RATE_LIMIT_ENABLED) is the backstop
# that still applies if the edge is bypassed.

resource "cloudflare_ruleset" "rate_limits" {
  count = var.cloudflare_enabled && var.cloudflare_rate_limit_enabled ? 1 : 0

  zone_id = var.cloudflare_zone_id
  name    = "${local.name_prefix} rate limits"
  kind    = "zone"
  phase   = "http_ratelimit"

  rules = [
    {
      ref         = "calendar_feed"
      description = "Calendar feed token guessing (unauthenticated surface)"
      expression  = "starts_with(http.request.uri.path, \"/api/calendar/\") or (http.host eq \"api.${var.app_domain}\" and starts_with(http.request.uri.path, \"/calendar/\"))"
      action      = "block"
      ratelimit = {
        characteristics     = ["ip.src", "cf.colo.id"]
        period              = 60
        requests_per_period = 60
        mitigation_timeout  = 600
      }
    },
    {
      ref         = "auth_surface"
      description = "Auth plane: claim-token spray and login abuse"
      expression  = "starts_with(http.request.uri.path, \"/api/auth/\") or (http.host eq \"api.${var.app_domain}\" and starts_with(http.request.uri.path, \"/auth/\"))"
      action      = "block"
      ratelimit = {
        characteristics     = ["ip.src", "cf.colo.id"]
        period              = 60
        requests_per_period = 20
        mitigation_timeout  = 600
      }
    },
    {
      ref         = "twh_import"
      description = "Bulk import: expensive request path"
      expression  = "starts_with(http.request.uri.path, \"/api/import/\") or (http.host eq \"api.${var.app_domain}\" and starts_with(http.request.uri.path, \"/import/\"))"
      action      = "block"
      ratelimit = {
        characteristics     = ["ip.src", "cf.colo.id"]
        period              = 60
        requests_per_period = 5
        mitigation_timeout  = 600
      }
    }
  ]
}

# --- Cloudflare Access belt for the platform control plane (GH-117) ----------
# One Access application covers the admin console subdomain and the /platform API
# paths on both API shapes. The backend independently verifies the resulting
# Cf-Access-Jwt-Assertion (CF_ACCESS_TEAM_DOMAIN / CF_ACCESS_AUD env in gcp.tf),
# so passing the edge policy alone is not enough — and vice versa.
#
# NOTE for the admin console's XHR calls to api.<domain>: in the Zero Trust
# dashboard set the Access application's cookie settings to the parent domain
# (.${var.app_domain}) — or serve the admin API same-origin — so the browser
# attaches the Access session to API requests.

resource "cloudflare_zero_trust_access_policy" "platform_staff" {
  count = var.cloudflare_enabled && var.cf_access_enabled ? 1 : 0

  account_id = var.cloudflare_account_id
  name       = "${local.name_prefix}-platform-staff"
  decision   = "allow"

  include = [
    for email in var.cf_access_allowed_emails : {
      email = { email = email }
    }
  ]
}

resource "cloudflare_zero_trust_access_application" "platform" {
  count = var.cloudflare_enabled && var.cf_access_enabled ? 1 : 0

  zone_id          = var.cloudflare_zone_id
  name             = "${local.name_prefix}-platform"
  type             = "self_hosted"
  domain           = "admin.${var.app_domain}"
  session_duration = "24h"

  destinations = [
    { uri = "admin.${var.app_domain}" },
    { uri = "api.${var.app_domain}/platform" },
    { uri = "${var.app_domain}/api/platform" }
  ]

  policies = [
    {
      id         = cloudflare_zero_trust_access_policy.platform_staff[0].id
      precedence = 1
    }
  ]
}

check "cf_access_configuration" {
  assert {
    condition     = !var.cf_access_enabled || (var.cf_access_team_domain != null && length(var.cf_access_allowed_emails) > 0)
    error_message = "cf_access_enabled requires cf_access_team_domain and at least one cf_access_allowed_emails entry."
  }
}
