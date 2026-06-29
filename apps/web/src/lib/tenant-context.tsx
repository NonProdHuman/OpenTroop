"use client"

import { createContext, useCallback, useContext, useEffect, useState } from "react"
import { useQueryClient } from "@tanstack/react-query"

import { useAuth } from "@clerk/nextjs"
import type { Membership } from "@/types/api"

const STORAGE_KEY = "opentroop.active_tenant"
const DEFAULT_TENANT = process.env.NEXT_PUBLIC_TENANT_ID ?? ""
const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
const CLERK_JWT_TEMPLATE = process.env.NEXT_PUBLIC_CLERK_JWT_TEMPLATE || undefined

interface TenantContextValue {
  activeTenantId: string
  setActiveTenantId: (id: string) => void
}

const TenantContext = createContext<TenantContextValue>({
  activeTenantId: DEFAULT_TENANT,
  setActiveTenantId: () => {},
})

export function TenantProvider({ children }: { children: React.ReactNode }) {
  const [activeTenantId, setActiveTenantIdState] = useState<string>(DEFAULT_TENANT)
  const { getToken, isLoaded: authLoaded, isSignedIn } = useAuth()
  const queryClient = useQueryClient()

  // Hydrate from localStorage on mount (avoids SSR mismatch) as an initial fallback.
  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY)
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (stored) setActiveTenantIdState(stored)
  }, [])

  // Resolve subdomain tenant on mount or auth change
  useEffect(() => {
    if (!authLoaded || !isSignedIn) return

    async function resolveTenant() {
      try {
        const token = await getToken(
          CLERK_JWT_TEMPLATE ? { template: CLERK_JWT_TEMPLATE } : undefined,
        )
        const res = await fetch(`${BASE}/auth/memberships`, {
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
        })
        if (!res.ok) return

        const memberships: Membership[] = await res.json()
        if (!memberships || memberships.length === 0) return

        const hostname = window.location.hostname
        const parts = hostname.split(".")

        let currentSubdomain: string | null = null
        if (
          hostname !== "localhost" &&
          hostname !== "127.0.0.1" &&
          !hostname.startsWith("192.168.") &&
          !hostname.endsWith(".local") &&
          parts.length > 2
        ) {
          currentSubdomain = parts[0]
        }

        if (currentSubdomain) {
          const matched = memberships.find((m) => m.tenant_slug === currentSubdomain)
          if (matched && activeTenantId !== matched.tenant_id) {
            setActiveTenantIdState(matched.tenant_id)
            localStorage.setItem(STORAGE_KEY, matched.tenant_id)
          }
        } else {
          // No subdomain, verify or select default
          const stored = localStorage.getItem(STORAGE_KEY)
          if (stored) {
            const exists = memberships.some((m) => m.tenant_id === stored)
            if (exists) {
              if (activeTenantId !== stored) {
                setActiveTenantIdState(stored)
              }
              return
            }
          }
          // Default to first membership
          if (activeTenantId !== memberships[0].tenant_id) {
            setActiveTenantIdState(memberships[0].tenant_id)
            localStorage.setItem(STORAGE_KEY, memberships[0].tenant_id)
          }
        }
      } catch (err) {
        console.error("Failed to resolve tenant from memberships:", err)
      }
    }

    resolveTenant()
  }, [authLoaded, isSignedIn, getToken, activeTenantId])

  const setActiveTenantId = useCallback(
    (id: string) => {
      setActiveTenantIdState(id)
      localStorage.setItem(STORAGE_KEY, id)
      queryClient.clear()
    },
    [queryClient],
  )

  return (
    <TenantContext.Provider value={{ activeTenantId, setActiveTenantId }}>
      {children}
    </TenantContext.Provider>
  )
}

export function useActiveTenant(): TenantContextValue {
  return useContext(TenantContext)
}
