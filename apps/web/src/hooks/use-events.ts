"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useApi } from "@/lib/api"
import type { Event, EventType, Location } from "@/types/api"

export function useEvents() {
  const { request } = useApi()
  return useQuery({
    queryKey: ["events"],
    queryFn: () => request<Event[]>("/events/"),
  })
}

export function useEventTypes() {
  const { request } = useApi()
  return useQuery({
    queryKey: ["event-types"],
    queryFn: () => request<EventType[]>("/event-types/"),
  })
}

export function useLocations() {
  const { request } = useApi()
  return useQuery({
    queryKey: ["locations"],
    queryFn: () => request<Location[]>("/locations/"),
  })
}

export function useCreateEvent() {
  const { request } = useApi()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: Partial<Event>) =>
      request<Event>("/events/", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["events"] })
    },
  })
}
