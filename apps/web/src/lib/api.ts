"use client"

import { useAuth } from "@clerk/nextjs"
import { useCallback } from "react"
import { useActiveTenant } from "@/lib/tenant-context"

const BASE = "/api"
const CLERK_JWT_TEMPLATE = process.env.NEXT_PUBLIC_CLERK_JWT_TEMPLATE || undefined

/** A non-2xx API response. Carries the HTTP status so callers can branch on
 * semantics (409 conflict, 403 forbidden, …) instead of parsing the message. */
export class ApiError extends Error {
  readonly status: number

  constructor(status: number, detail: string) {
    super(`${status}: ${detail}`)
    this.name = "ApiError"
    this.status = status
  }
}

const GENERIC_ERROR = "Something went wrong — please try again."
const NETWORK_ERROR = "Could not reach the backend — is the server running?"

/**
 * Map a thrown request error to a user-facing message. `byStatus` supplies
 * page-specific copy for HTTP statuses (e.g. a 409 conflict explanation);
 * network failures (fetch rejects with a TypeError before any response) and
 * unmatched statuses fall back to generic copy.
 */
export function apiErrorMessage(err: unknown, byStatus?: Record<number, string>): string {
  if (err instanceof ApiError) {
    return byStatus?.[err.status] ?? GENERIC_ERROR
  }
  if (err instanceof TypeError) {
    return NETWORK_ERROR
  }
  return GENERIC_ERROR
}

export function useApi() {
  const { getToken } = useAuth()
  const { activeTenantId } = useActiveTenant()

  const request = useCallback(
    async <T>(path: string, init?: RequestInit): Promise<T> => {
      // On the public demo host there's no Clerk session; getToken() resolves to
      // null (or, defensively, may reject). Swallow either so the request goes out
      // with no Authorization header — the backend then resolves the read-only demo
      // viewer (GH-246). Everywhere else this is a normal authenticated token.
      const token = await getToken(
        CLERK_JWT_TEMPLATE ? { template: CLERK_JWT_TEMPLATE } : undefined,
      ).catch(() => null)
      const isFormData = init?.body instanceof FormData
      const res = await fetch(`${BASE}${path}`, {
        ...init,
        headers: {
          ...(isFormData ? {} : { "Content-Type": "application/json" }),
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          // Tenant scope. The backend resolves tenant from the subdomain first
          // (x-forwarded-host) and falls back to this header — which is what makes
          // plain localhost:3000 work in dev without wildcard DNS or https.
          ...(activeTenantId ? { "X-Tenant-ID": activeTenantId } : {}),
          ...(init?.headers ?? {}),
        },
      })
      if (!res.ok) {
        const detail = await res.text().catch(() => res.statusText)
        throw new ApiError(res.status, detail)
      }
      // 204 No Content (and other empty bodies) have nothing to parse.
      if (res.status === 204 || res.headers.get("content-length") === "0") {
        return undefined as T
      }
      return res.json() as Promise<T>
    },
    [getToken, activeTenantId],
  )

  /**
   * Fetch a non-JSON attachment (e.g. a streamed CSV report). Returns the raw
   * Blob; the auth token + tenant header ride the request the same way `request`
   * sends them, which a bare `<a href>` navigation can't do.
   */
  const requestBlob = useCallback(
    async (path: string, init?: RequestInit): Promise<Blob> => {
      // On the public demo host there's no Clerk session; getToken() resolves to
      // null (or, defensively, may reject). Swallow either so the request goes out
      // with no Authorization header — the backend then resolves the read-only demo
      // viewer (GH-246). Everywhere else this is a normal authenticated token.
      const token = await getToken(
        CLERK_JWT_TEMPLATE ? { template: CLERK_JWT_TEMPLATE } : undefined,
      ).catch(() => null)
      const res = await fetch(`${BASE}${path}`, {
        ...init,
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(activeTenantId ? { "X-Tenant-ID": activeTenantId } : {}),
          ...(init?.headers ?? {}),
        },
      })
      if (!res.ok) {
        const detail = await res.text().catch(() => res.statusText)
        throw new ApiError(res.status, detail)
      }
      return res.blob()
    },
    [getToken, activeTenantId],
  )

  return { request, requestBlob }
}
