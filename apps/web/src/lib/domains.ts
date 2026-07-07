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

// Host that serves the anonymous read-only public demo (GH-246), e.g.
// "demo.opentroop.dev". Empty (default) = demo mode is off everywhere. This is the
// frontend mirror of the backend's DEMO_TENANT_SLUG: on this exact host the
// middleware skips auth.protect() and the app renders for signed-out visitors.
export const DEMO_HOST = process.env.NEXT_PUBLIC_DEMO_HOST || ""

// True only on the client, and only when the current host is the configured demo
// host. Server-side it always returns false (no window), so callers must tolerate a
// first render of `false` — see DemoBanner, which flips on mount to avoid a
// hydration mismatch.
export function isDemoHost(): boolean {
  if (!DEMO_HOST || typeof window === "undefined") return false
  return window.location.host === DEMO_HOST
}
