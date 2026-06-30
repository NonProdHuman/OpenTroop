"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useApi } from "@/lib/api"
import { useActiveTenant } from "@/lib/tenant-context"
import type {
  Event,
  EventParticipant,
  EventParticipantCounts,
  EventType,
  Location,
  RsvpStatus,
  TenantSettings,
} from "@/types/api"

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

export function useEventParticipants(eventId: string | null) {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: [activeTenantId, "event-participants", eventId],
    queryFn: () => request<EventParticipant[]>(`/events/${eventId}/participants`),
    enabled: eventId !== null && Boolean(activeTenantId),
  })
}

export function useEventCounts(eventId: string | null) {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: [activeTenantId, "event-counts", eventId],
    queryFn: () => request<EventParticipantCounts>(`/events/${eventId}/counts`),
    enabled: eventId !== null && Boolean(activeTenantId),
  })
}

type ParticipantBody = {
  rsvp_status?: RsvpStatus
  driver?: boolean
  drives_to?: boolean
  drives_from?: boolean
  seat_count?: number | null
  guest_count?: number
  comment?: string | null
}

export function useAddParticipant(eventId: string) {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  const queryClient = useQueryClient()
  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: [activeTenantId, "event-participants", eventId] })
    queryClient.invalidateQueries({ queryKey: [activeTenantId, "event-counts", eventId] })
  }
  return useMutation({
    mutationFn: (body: ParticipantBody & { member_id: string }) =>
      request<EventParticipant>(`/events/${eventId}/participants`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: invalidate,
  })
}

export function useUpdateParticipant(eventId: string) {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  const queryClient = useQueryClient()
  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: [activeTenantId, "event-participants", eventId] })
    queryClient.invalidateQueries({ queryKey: [activeTenantId, "event-counts", eventId] })
  }
  return useMutation({
    mutationFn: ({ memberId, ...body }: ParticipantBody & { memberId: string }) =>
      request<EventParticipant>(`/events/${eventId}/participants/${memberId}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      }),
    onSuccess: invalidate,
  })
}

export function useGrantPermission(eventId: string) {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ memberId, signature }: { memberId: string; signature: string }) =>
      request<EventParticipant>(
        `/events/${eventId}/participants/${memberId}/permission`,
        { method: "POST", body: JSON.stringify({ signature }) },
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [activeTenantId, "event-participants", eventId] })
    },
  })
}

export function useTenantSettings() {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: [activeTenantId, "tenant-settings"],
    queryFn: () => request<TenantSettings>("/tenant/settings/"),
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
