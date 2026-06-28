resource "cloudflare_dns_record" "apex" {
  count = var.cloudflare_enabled ? 1 : 0

  zone_id = var.cloudflare_zone_id
  name    = local.cloudflare_app_record
  type    = "CNAME"
  content = trimprefix(google_cloud_run_v2_service.web.uri, "https://")
  ttl     = 1
  proxied = true
}

resource "cloudflare_dns_record" "wildcard" {
  count = var.cloudflare_enabled ? 1 : 0

  zone_id = var.cloudflare_zone_id
  name    = local.cloudflare_wildcard_record
  type    = "CNAME"
  content = var.app_domain
  ttl     = 1
  proxied = true
}

resource "cloudflare_dns_record" "api" {
  count = var.cloudflare_enabled ? 1 : 0

  zone_id = var.cloudflare_zone_id
  name    = local.cloudflare_api_record
  type    = "CNAME"
  content = trimprefix(google_cloud_run_v2_service.api.uri, "https://")
  ttl     = 1
  proxied = true
}

resource "cloudflare_workers_script" "proxy" {
  count = var.cloudflare_enabled ? 1 : 0

  account_id         = var.cloudflare_account_id
  script_name        = local.worker_name
  content            = file("${path.module}/worker/opentroop-proxy.js")
  main_module        = "opentroop-proxy.js"
  compatibility_date = "2024-04-03"

  bindings = [
    {
      name = "APP_DOMAIN"
      type = "plain_text"
      text = var.app_domain
    },
    {
      name = "API_ORIGIN"
      type = "plain_text"
      text = google_cloud_run_v2_service.api.uri
    },
    {
      name = "WEB_ORIGIN"
      type = "plain_text"
      text = google_cloud_run_v2_service.web.uri
    }
  ]
}

resource "cloudflare_workers_route" "apex" {
  count = var.cloudflare_enabled ? 1 : 0

  zone_id = var.cloudflare_zone_id
  pattern = "${var.app_domain}/*"
  script  = cloudflare_workers_script.proxy[0].script_name
}

resource "cloudflare_workers_route" "wildcard" {
  count = var.cloudflare_enabled ? 1 : 0

  zone_id = var.cloudflare_zone_id
  pattern = "*.${var.app_domain}/*"
  script  = cloudflare_workers_script.proxy[0].script_name
}
