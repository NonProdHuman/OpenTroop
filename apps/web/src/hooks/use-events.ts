"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { queryKeys } from "@/lib/query-keys"
import { useApi } from "@/lib/api"
import { useActiveTenant } from "@/lib/tenant-context"
import type {
  Event,
  EventAudience,
  EventOrganizer,
  EventParticipant,
  EventParticipantCounts,
  EventType,
  RsvpStatus,
} from "@/types/api"

export function useEvents() {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: queryKeys.events(activeTenantId),
    queryFn: () => request<Event[]>("/events"),
    enabled: Boolean(activeTenantId),
  })
}

export function useEvent(id: string | null) {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: queryKeys.event(activeTenantId, id),
    queryFn: () => request<Event>(`/events/${id}`),
    enabled: id !== null && Boolean(activeTenantId),
  })
}

export function useEventTypes() {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: queryKeys.eventTypes(activeTenantId),
    queryFn: () => request<EventType[]>("/event-types"),
    enabled: Boolean(activeTenantId),
  })
}

export function useEventParticipants(eventId: string | null) {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: queryKeys.eventParticipants(activeTenantId, eventId),
    queryFn: () => request<EventParticipant[]>(`/events/${eventId}/participants`),
    enabled: eventId !== null && Boolean(activeTenantId),
  })
}

export function useEventCounts(eventId: string | null) {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: queryKeys.eventCounts(activeTenantId, eventId),
    queryFn: () => request<EventParticipantCounts>(`/events/${eventId}/counts`),
    enabled: eventId !== null && Boolean(activeTenantId),
  })
}

export type ParticipantBody = {
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
    queryClient.invalidateQueries({ queryKey: queryKeys.eventParticipants(activeTenantId, eventId) })
    queryClient.invalidateQueries({ queryKey: queryKeys.eventCounts(activeTenantId, eventId) })
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
    queryClient.invalidateQueries({ queryKey: queryKeys.eventParticipants(activeTenantId, eventId) })
    queryClient.invalidateQueries({ queryKey: queryKeys.eventCounts(activeTenantId, eventId) })
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
      queryClient.invalidateQueries({ queryKey: queryKeys.eventParticipants(activeTenantId, eventId) })
    },
  })
}

export function useCreateEvent() {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: Partial<Event>) =>
      request<Event>("/events", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.events(activeTenantId) })
    },
  })
}

export function useUpdateEvent() {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<Event> }) =>
      request<Event>(`/events/${id}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    onSuccess: (updated, { id }) => {
      queryClient.setQueryData(queryKeys.event(activeTenantId, id), updated)
      queryClient.invalidateQueries({ queryKey: queryKeys.events(activeTenantId) })
    },
  })
}

// ── Audiences (visibility groups) ─────────────────────────────────────────────

export function useEventAudiences(eventId: string | null) {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: queryKeys.eventAudiences(activeTenantId, eventId),
    queryFn: () => request<EventAudience[]>(`/events/${eventId}/audiences`),
    enabled: eventId !== null && Boolean(activeTenantId),
  })
}

export function useAddEventAudience(eventId: string) {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (groupId: string) =>
      request<EventAudience>(`/events/${eventId}/audiences`, {
        method: "POST",
        body: JSON.stringify({ group_id: groupId }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.eventAudiences(activeTenantId, eventId) })
    },
  })
}

export function useRemoveEventAudience(eventId: string) {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (groupId: string) =>
      request(`/events/${eventId}/audiences/${groupId}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.eventAudiences(activeTenantId, eventId) })
    },
  })
}

// ── Organizers ─────────────────────────────────────────────────────────────────

export function useEventOrganizers(eventId: string | null) {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: queryKeys.eventOrganizers(activeTenantId, eventId),
    queryFn: () => request<EventOrganizer[]>(`/events/${eventId}/organizers`),
    enabled: eventId !== null && Boolean(activeTenantId),
  })
}

export function useAddEventOrganizer(eventId: string) {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (memberId: string) =>
      request<EventOrganizer>(`/events/${eventId}/organizers`, {
        method: "POST",
        body: JSON.stringify({ member_id: memberId }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.eventOrganizers(activeTenantId, eventId) })
    },
  })
}

export function useRemoveEventOrganizer(eventId: string) {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (memberId: string) =>
      request(`/events/${eventId}/organizers/${memberId}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.eventOrganizers(activeTenantId, eventId) })
    },
  })
}
