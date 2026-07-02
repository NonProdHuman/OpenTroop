"use client"

import { useQuery } from "@tanstack/react-query"
import { queryKeys } from "@/lib/query-keys"
import { useApi } from "@/lib/api"
import { useActiveTenant } from "@/lib/tenant-context"
import type { TenantSettings } from "@/types/api"

export function useTenantSettings() {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: queryKeys.tenantSettings(activeTenantId),
    queryFn: () => request<TenantSettings>("/tenant/settings"),
    enabled: Boolean(activeTenantId),
  })
}
