"use client"

import { useAuth } from "@clerk/nextjs"
import { useCallback } from "react"

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
const TENANT_ID = process.env.NEXT_PUBLIC_TENANT_ID ?? ""

export function useApi() {
  const { getToken } = useAuth()

  const request = useCallback(
    async <T>(path: string, init?: RequestInit): Promise<T> => {
      const token = await getToken()
      const res = await fetch(`${BASE}${path}`, {
        ...init,
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(TENANT_ID ? { "X-Tenant-ID": TENANT_ID } : {}),
          ...(init?.headers ?? {}),
        },
      })
      if (!res.ok) {
        const detail = await res.text().catch(() => res.statusText)
        throw new Error(`${res.status}: ${detail}`)
      }
      // 204 No Content (and other empty bodies) have nothing to parse.
      if (res.status === 204 || res.headers.get("content-length") === "0") {
        return undefined as T
      }
      return res.json() as Promise<T>
    },
    [getToken],
  )

  return { request }
}
