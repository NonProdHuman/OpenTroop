import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react"
import * as SecureStore from "expo-secure-store"
import type { Membership } from "./types"

export const ACTIVE_TENANT_KEY = "opentroop.active-tenant"
export const KNOWN_TENANTS_KEY = "opentroop.known-tenants"

/** Tenant ids that ever had a local database — the sign-out wipe list (GH-153 §C5). */
export async function getKnownTenantIds(): Promise<string[]> {
  try {
    const stored = await SecureStore.getItemAsync(KNOWN_TENANTS_KEY)
    return stored ? (JSON.parse(stored) as string[]) : []
  } catch {
    return []
  }
}

async function rememberTenant(tenantId: string): Promise<void> {
  const known = await getKnownTenantIds()
  if (!known.includes(tenantId)) {
    await SecureStore.setItemAsync(KNOWN_TENANTS_KEY, JSON.stringify([...known, tenantId]))
  }
}

type TenantContextValue = {
  /** The selected troop, or null before first selection. */
  activeTenant: Membership | null
  setActiveTenant: (membership: Membership | null) => void
  /** False until the persisted selection has been read back from SecureStore. */
  isHydrated: boolean
}

const TenantContext = createContext<TenantContextValue | null>(null)

/**
 * Holds the active troop for the session and persists it across launches.
 * Mirrors the web app's tenant context; per GH-153 §C4 only the active tenant
 * ever syncs, and the M4 data layer keys its database file off this value.
 */
export function TenantProvider({ children }: { children: ReactNode }) {
  const [activeTenant, setActiveTenantState] = useState<Membership | null>(null)
  const [isHydrated, setIsHydrated] = useState(false)

  useEffect(() => {
    let cancelled = false
    SecureStore.getItemAsync(ACTIVE_TENANT_KEY)
      .then((stored) => {
        if (!cancelled && stored) setActiveTenantState(JSON.parse(stored) as Membership)
      })
      .catch(() => undefined) // unreadable persisted value: start unselected
      .finally(() => {
        if (!cancelled) setIsHydrated(true)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const setActiveTenant = useCallback((membership: Membership | null) => {
    setActiveTenantState(membership)
    if (membership) {
      void SecureStore.setItemAsync(ACTIVE_TENANT_KEY, JSON.stringify(membership))
      void rememberTenant(membership.tenant_id)
    } else {
      void SecureStore.deleteItemAsync(ACTIVE_TENANT_KEY)
    }
  }, [])

  const value = useMemo(
    () => ({ activeTenant, setActiveTenant, isHydrated }),
    [activeTenant, setActiveTenant, isHydrated],
  )
  return <TenantContext.Provider value={value}>{children}</TenantContext.Provider>
}

export function useActiveTenant(): TenantContextValue {
  const ctx = useContext(TenantContext)
  if (!ctx) throw new Error("useActiveTenant must be used within TenantProvider")
  return ctx
}
