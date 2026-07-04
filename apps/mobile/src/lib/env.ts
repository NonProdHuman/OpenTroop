/** Compile-time app configuration (EXPO_PUBLIC_* env, baked into the bundle). */

export const CLERK_PUBLISHABLE_KEY = process.env.EXPO_PUBLIC_CLERK_PUBLISHABLE_KEY ?? ""

/** Dev override: a single API origin (X-Tenant-ID header mode). */
export const API_URL = process.env.EXPO_PUBLIC_API_URL ?? ""

/** SaaS mode: tenant APIs live at https://<slug>.<domain>/api (subdomain routing). */
export const APP_DOMAIN = process.env.EXPO_PUBLIC_APP_DOMAIN ?? ""

/**
 * Resolve the API base URL for a tenant (or for tenant-less endpoints like
 * /auth/memberships when `slug` is null).
 *
 * Two modes, mirroring the backend's tenant resolution (app/core/tenant.py):
 * - `EXPO_PUBLIC_API_URL` set (local dev): one origin for everything; requests
 *   carry X-Tenant-ID (the dev backend runs ALLOW_TENANT_ID_HEADER=true).
 * - otherwise (SaaS): https://<slug>.<domain>/api so tenant resolution is
 *   subdomain-only, matching ALLOW_TENANT_ID_HEADER=false in production.
 */
export function apiBaseUrl(slug: string | null): string {
  if (API_URL) return API_URL
  if (!APP_DOMAIN) {
    throw new Error(
      "Set EXPO_PUBLIC_API_URL (dev) or EXPO_PUBLIC_APP_DOMAIN (production) — see .env.example",
    )
  }
  return slug ? `https://${slug}.${APP_DOMAIN}/api` : `https://${APP_DOMAIN}/api`
}

/** Whether tenant scoping should be sent as an X-Tenant-ID header (dev mode). */
export function usesTenantHeader(): boolean {
  return Boolean(API_URL)
}
