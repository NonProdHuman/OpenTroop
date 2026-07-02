// Single source of truth for the app's root domain — the frontend mirror of the
// backend's APP_DOMAIN. Local dev: "localhost:3000". Production: e.g. "opentroop.dev".
// Tenants are subdomains of this (troop123.<root>), and the platform console is
// admin.<root>. Nothing else should hardcode the domain.
export const APP_DOMAIN = process.env.NEXT_PUBLIC_APP_DOMAIN || "localhost:3000"

export function getRootDomain(): string {
  return APP_DOMAIN
}

function protocol(): string {
  // On the client, mirror the actual scheme. On the server we can't read it, so derive
  // it deterministically from the domain — http for local dev, https everywhere else —
  // so the SSR'd href matches what the client renders and doesn't trip a hydration
  // mismatch (React won't patch attribute differences).
  if (typeof window !== "undefined") return window.location.protocol
  return APP_DOMAIN.startsWith("localhost") ? "http:" : "https:"
}

export function getAdminUrl(path: string = ""): string {
  return `${protocol()}//admin.${APP_DOMAIN}${path}`
}

export function getLandingUrl(path: string = ""): string {
  return `${protocol()}//${APP_DOMAIN}${path}`
}

export function getTenantUrl(slug: string, path: string = ""): string {
  return `${protocol()}//${slug}.${APP_DOMAIN}${path}`
}
