"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useApi } from "@/lib/api"
import { useActiveTenant } from "@/lib/tenant-context"
import type { Event, EventType, Location } from "@/types/api"

export function useEvents() {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: [activeTenantId, "events"],
    queryFn: () => request<Event[]>("/events/"),
    enabled: Boolean(activeTenantId),
  })
}

export function useEventTypes() {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: [activeTenantId, "event-types"],
    queryFn: () => request<EventType[]>("/event-types/"),
    enabled: Boolean(activeTenantId),
  })
}

export function useLocations() {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: [activeTenantId, "locations"],
    queryFn: () => request<Location[]>("/locations/"),
    enabled: Boolean(activeTenantId),
  })
}

export function useCreateEvent() {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: Partial<Event>) =>
      request<Event>("/events/", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [activeTenantId, "events"] })
    },
  })
}
