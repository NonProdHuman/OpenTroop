/**
 * Builds the URL to send a signed-in user to their tenant's subdomain after the
 * landing page resolves their membership. Uses the single configured root domain
 * (see lib/domains.ts) so there's no hardcoded domain here.
 */
import { getTenantUrl } from "./domains"

export function getTenantRedirectUrl(slug: string, path: string = "/members"): string | null {
  if (typeof window === "undefined") return null
  return getTenantUrl(slug, path)
}
