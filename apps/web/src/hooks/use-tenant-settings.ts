"use client"

import { useQuery } from "@tanstack/react-query"
import { useApi } from "@/lib/api"
import { useActiveTenant } from "@/lib/tenant-context"
import type { TenantSettings } from "@/types/api"

export function useTenantSettings() {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: [activeTenantId, "tenant-settings"],
    queryFn: () => request<TenantSettings>("/tenant/settings"),
    enabled: Boolean(activeTenantId),
  })
}
