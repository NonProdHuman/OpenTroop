"use client"

import { useQuery } from "@tanstack/react-query"
import { useApi } from "@/lib/api"
import type { Event, EventType } from "@/types/api"

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
