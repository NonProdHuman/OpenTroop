"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { queryKeys } from "@/lib/query-keys"
import { useApi } from "@/lib/api"
import { useActiveTenant } from "@/lib/tenant-context"
import type { EventSlot, EventSlotCreate, EventSlotSignup, EventSlotUpdate } from "@/types/api"

export function useEventSlots(eventId: string | null) {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: queryKeys.eventSlots(activeTenantId, eventId),
    queryFn: () => request<EventSlot[]>(`/events/${eventId}/slots`),
    enabled: eventId !== null && Boolean(activeTenantId),
  })
}

export function useCreateSlot(eventId: string) {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: EventSlotCreate) =>
      request<EventSlot>(`/events/${eventId}/slots`, {
        method: "POST",
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.eventSlots(activeTenantId, eventId) })
    },
  })
}

export function useUpdateSlot(eventId: string) {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ slotId, data }: { slotId: string; data: EventSlotUpdate }) =>
      request<EventSlot>(`/events/${eventId}/slots/${slotId}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.eventSlots(activeTenantId, eventId) })
    },
  })
}

export function useDeleteSlot(eventId: string) {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (slotId: string) =>
      request(`/events/${eventId}/slots/${slotId}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.eventSlots(activeTenantId, eventId) })
    },
  })
}

export function useJoinSlot(eventId: string) {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ slotId, memberId }: { slotId: string; memberId: string }) =>
      request<EventSlotSignup>(`/events/${eventId}/slots/${slotId}/signups`, {
        method: "POST",
        body: JSON.stringify({ member_id: memberId }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.eventSlots(activeTenantId, eventId) })
    },
  })
}

export function useLeaveSlot(eventId: string) {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ slotId, memberId }: { slotId: string; memberId: string }) =>
      request(`/events/${eventId}/slots/${slotId}/signups/${memberId}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.eventSlots(activeTenantId, eventId) })
    },
  })
}
