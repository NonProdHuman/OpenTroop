"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useApi } from "@/lib/api"
import { useActiveTenant } from "@/lib/tenant-context"
import type { NotificationPreferences, NotificationPreferencesUpdate } from "@/types/api"

const PATH = "/members/me/notification-preferences"

/** The signed-in member's own announcement email preference (GH-218). */
export function useNotificationPreferences() {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: [activeTenantId, "notification-preferences"],
    queryFn: () => request<NotificationPreferences>(PATH),
    enabled: Boolean(activeTenantId),
  })
}

export function useUpdateNotificationPreferences() {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: NotificationPreferencesUpdate) =>
      request<NotificationPreferences>(PATH, {
        method: "PATCH",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [activeTenantId, "notification-preferences"] })
    },
  })
}
