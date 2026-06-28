"use client"

import { createContext, useCallback, useContext, useEffect, useState } from "react"
import { useQueryClient } from "@tanstack/react-query"

const STORAGE_KEY = "opentroop.active_tenant"
const DEFAULT_TENANT = process.env.NEXT_PUBLIC_TENANT_ID ?? ""

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

  // Hydrate from localStorage on mount (avoids SSR mismatch).
  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY)
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (stored) setActiveTenantIdState(stored)
  }, [])

  const queryClient = useQueryClient()

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
