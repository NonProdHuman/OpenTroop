"use client"

import { useQuery } from "@tanstack/react-query"
import { useApi } from "@/lib/api"
import { useActiveTenant } from "@/lib/tenant-context"
import type { Permission, Session } from "@/types/api"

export function useSession() {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: ["session", activeTenantId],
    queryFn: () => request<Session>("/auth/session"),
    enabled: Boolean(activeTenantId),
  })
}

export function usePermissions() {
  const { data, isLoading } = useSession()
  const set = new Set(data?.permissions ?? [])
  return {
    has: (p: Permission) => set.has(p),
    isMember: data?.member != null,
    isLoading,
  }
}
