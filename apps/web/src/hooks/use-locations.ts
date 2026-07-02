"use client"

import { useQuery } from "@tanstack/react-query"
import { queryKeys } from "@/lib/query-keys"
import { useApi } from "@/lib/api"
import { useActiveTenant } from "@/lib/tenant-context"
import type { Location } from "@/types/api"

export function useLocations() {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: queryKeys.locations(activeTenantId),
    queryFn: () => request<Location[]>("/locations"),
    enabled: Boolean(activeTenantId),
  })
}
