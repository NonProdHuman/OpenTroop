export function getRootDomain(hostname?: string): string {
  // Try to use provided hostname, fallback to window.location if in browser
  const host = hostname || (typeof window !== "undefined" ? window.location.hostname : "opentroop.dev")

  if (host.includes("localhost") || host.includes("127.0.0.1")) {
    // Determine the port if running locally
    const port = typeof window !== "undefined" && window.location.port ? `:${window.location.port}` : ":3000"
    return `opentroop.localhost${port}`
  }

  // If we are on vercel preview URLs or similar, this might need expanding,
  // but for production it's opentroop.dev
  return "opentroop.dev"
}

export function getAdminUrl(path: string = ""): string {
  const root = getRootDomain()
  const protocol = typeof window !== "undefined" ? window.location.protocol : "https:"
  return `${protocol}//admin.${root}${path}`
}

export function getLandingUrl(path: string = ""): string {
  const root = getRootDomain()
  const protocol = typeof window !== "undefined" ? window.location.protocol : "https:"
  return `${protocol}//${root}${path}`
}

export function getTenantUrl(slug: string, path: string = ""): string {
  const root = getRootDomain()
  const protocol = typeof window !== "undefined" ? window.location.protocol : "https:"
  return `${protocol}//${slug}.${root}${path}`
}
