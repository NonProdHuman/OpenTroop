resource "cloudflare_record" "apex" {
  count = var.cloudflare_enabled ? 1 : 0

  zone_id = var.cloudflare_zone_id
  name    = local.cloudflare_app_record
  type    = "CNAME"
  value   = trimprefix(google_cloud_run_v2_service.web.uri, "https://")
  proxied = true
}

resource "cloudflare_record" "wildcard" {
  count = var.cloudflare_enabled ? 1 : 0

  zone_id = var.cloudflare_zone_id
  name    = local.cloudflare_wildcard_record
  type    = "CNAME"
  value   = var.app_domain
  proxied = true
}

resource "cloudflare_record" "api" {
  count = var.cloudflare_enabled ? 1 : 0

  zone_id = var.cloudflare_zone_id
  name    = local.cloudflare_api_record
  type    = "CNAME"
  value   = trimprefix(google_cloud_run_v2_service.api.uri, "https://")
  proxied = true
}

resource "cloudflare_workers_script" "proxy" {
  count = var.cloudflare_enabled ? 1 : 0

  account_id         = var.cloudflare_account_id
  name               = local.worker_name
  content            = file("${path.module}/worker/opentroop-proxy.js")
  module             = true
  compatibility_date = "2024-04-03"

  plain_text_binding {
    name = "APP_DOMAIN"
    text = var.app_domain
  }

  plain_text_binding {
    name = "API_ORIGIN"
    text = google_cloud_run_v2_service.api.uri
  }

  plain_text_binding {
    name = "WEB_ORIGIN"
    text = google_cloud_run_v2_service.web.uri
  }
}

resource "cloudflare_workers_route" "apex" {
  count = var.cloudflare_enabled ? 1 : 0

  zone_id     = var.cloudflare_zone_id
  pattern     = "${var.app_domain}/*"
  script_name = cloudflare_workers_script.proxy[0].name
}

resource "cloudflare_workers_route" "wildcard" {
  count = var.cloudflare_enabled ? 1 : 0

  zone_id     = var.cloudflare_zone_id
  pattern     = "*.${var.app_domain}/*"
  script_name = cloudflare_workers_script.proxy[0].name
}
