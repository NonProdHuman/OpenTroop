"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
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

export function useUpdateTenantSettings() {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (
      body: Partial<
        Pick<
          TenantSettings,
          "permission_message" | "advancement_mode" | "digest_day" | "digest_hour_utc"
        >
      >,
    ) =>
      request<TenantSettings>("/tenant/settings", {
        method: "PATCH",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tenantSettings(activeTenantId) })
    },
  })
}
