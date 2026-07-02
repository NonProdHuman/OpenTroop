"use client"

import { useQuery } from "@tanstack/react-query"
import { queryKeys } from "@/lib/query-keys"
import { useApi } from "@/lib/api"
import { useActiveTenant } from "@/lib/tenant-context"
import type { Permission, Session } from "@/types/api"

export function useSession(enabled = true) {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: queryKeys.session(activeTenantId),
    queryFn: () => request<Session>("/auth/session"),
    // /auth/session is tenant-scoped. Callers on a non-tenant surface (the platform
    // console) pass enabled=false so it isn't fetched where there is no tenant.
    enabled: enabled && Boolean(activeTenantId),
  })
}

export function usePermissions(enabled = true) {
  const { data, isLoading } = useSession(enabled)
  const set = new Set(data?.permissions ?? [])
  return {
    has: (p: Permission) => set.has(p),
    isMember: data?.member != null,
    isLoading,
  }
}
