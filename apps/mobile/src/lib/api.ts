import { useCallback } from "react"
import { useAuth } from "@clerk/clerk-expo"
import { apiBaseUrl } from "./env"

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
  let detail = response.statusText
  try {
    const body = (await response.json()) as { detail?: unknown }
    if (typeof body.detail === "string") detail = body.detail
  } catch {
    // non-JSON error body; keep the status text
  }
  return new ApiError(response.status, detail)
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
