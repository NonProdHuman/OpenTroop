"use client"

import { useQuery } from "@tanstack/react-query"
import { useApi } from "@/lib/api"
import { useActiveTenant } from "@/lib/tenant-context"
import type { FunctionalRole } from "@/types/api"

export function useFunctionalRoles() {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: [activeTenantId, "functional-roles"],
    queryFn: () => request<FunctionalRole[]>("/functional-roles/"),
    enabled: Boolean(activeTenantId),
  })
}
