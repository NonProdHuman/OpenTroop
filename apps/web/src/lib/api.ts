"use client"

import { useAuth } from "@clerk/nextjs"
import { useCallback } from "react"

const BASE = "/api"
const CLERK_JWT_TEMPLATE = process.env.NEXT_PUBLIC_CLERK_JWT_TEMPLATE || undefined

export function useApi() {
  const { getToken } = useAuth()

  const request = useCallback(
    async <T>(path: string, init?: RequestInit): Promise<T> => {
      const token = await getToken(
        CLERK_JWT_TEMPLATE ? { template: CLERK_JWT_TEMPLATE } : undefined,
      )
      const isFormData = init?.body instanceof FormData
      const res = await fetch(`${BASE}${path}`, {
        ...init,
        headers: {
          ...(isFormData ? {} : { "Content-Type": "application/json" }),
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
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
