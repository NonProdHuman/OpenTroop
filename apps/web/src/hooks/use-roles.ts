"use client"

import { useQuery } from "@tanstack/react-query"
import { useApi } from "@/lib/api"
import { useActiveTenant } from "@/lib/tenant-context"
import type { Role } from "@/types/api"

export function useRoles() {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: [activeTenantId, "roles"],
    queryFn: () => request<Role[]>("/roles/"),
    enabled: Boolean(activeTenantId),
  })
}
