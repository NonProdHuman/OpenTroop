import { useCallback } from "react"
import { useAuth } from "@clerk/clerk-expo"
import { apiBaseUrl } from "./env"
import { errorDetail } from "./http"
import { useSyncContext } from "./sync-context"

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message)
    this.name = "ApiError"
  }
}

async function parseError(response: Response): Promise<ApiError> {
  let body: unknown = null
  try {
    body = await response.json()
  } catch {
    // non-JSON error body; errorDetail falls back to the status
  }
  return new ApiError(response.status, errorDetail(body, response.status))
}

/** Tenant-less client for the auth surface (/auth/memberships, /auth/me). */
export function useAuthApi() {
  const { getToken } = useAuth()

  const request = useCallback(
    async <T>(path: string): Promise<T> => {
      const token = await getToken()
      const headers: Record<string, string> = { "Content-Type": "application/json" }
      if (token) headers.Authorization = `Bearer ${token}`
      const response = await fetch(`${apiBaseUrl(null)}${path}`, { headers })
      if (!response.ok) throw await parseError(response)
      return (await response.json()) as T
    },
    [getToken],
  )

  return { request }
}

/**
 * Tenant-bound client for every online feature surface (advancement, messaging,
 * groups, …). Wraps the sync context's authenticated `http` client and throws
 * `ApiError` on any >= 400 — the one HTTP calling convention feature hooks use.
 */
export function useApiRequest() {
  const { http } = useSyncContext()
  return useCallback(
    async <T>(path: string, init?: { method: string; body?: unknown }): Promise<T> => {
      if (!http) throw new ApiError(0, "No active troop")
      const response = await http(path, init ?? { method: "GET" })
      if (response.status >= 400) {
        throw new ApiError(response.status, errorDetail(response.body, response.status))
      }
      return response.body as T
    },
    [http],
  )
}
