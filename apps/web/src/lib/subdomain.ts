/**
 * Helper to generate a tenant-specific subdomain URL for deployed environments
 * while falling back to standard paths during local development.
 */
export function getTenantRedirectUrl(slug: string, path: string = "/members"): string | null {
  if (typeof window === "undefined") return null

  const hostname = window.location.hostname
  const port = window.location.port

  // Keep local development on single-domain routing (no wildcard DNS on localhost)
  if (
    hostname === "localhost" ||
    hostname === "127.0.0.1" ||
    hostname.startsWith("192.168.") ||
    hostname.endsWith(".local")
  ) {
    return null
  }

  const parts = hostname.split(".")
  let baseDomain = hostname

  // Extract base parent domain if on a subdomain (e.g. troop1.opentroop.dev -> opentroop.dev)
  if (parts.length > 2) {
    baseDomain = parts.slice(-2).join(".")
  }

  const portSuffix = port ? `:${port}` : ""
  // Preserve the current protocol so local dev (http) isn't forced onto https.
  const protocol = window.location.protocol // "http:" or "https:"
  return `${protocol}//${slug}.${baseDomain}${portSuffix}${path}`
}
