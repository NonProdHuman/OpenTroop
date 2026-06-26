"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useApi } from "@/lib/api"
import { useActiveTenant } from "@/lib/tenant-context"
import type { Member } from "@/types/api"

export function useMembers() {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: [activeTenantId, "members"],
    queryFn: () => request<Member[]>("/members/"),
    enabled: Boolean(activeTenantId),
  })
}

export function useMember(id: string | null) {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: [activeTenantId, "members", id],
    queryFn: () => request<Member>(`/members/${id}`),
    enabled: id !== null && Boolean(activeTenantId),
  })
}

export function useCreateMember() {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: Partial<Member>) =>
      request<Member>("/members/", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [activeTenantId, "members"] })
    },
  })
}

export function useUpdateMember() {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<Member> }) =>
      request<Member>(`/members/${id}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    onSuccess: (updated) => {
      queryClient.setQueryData([activeTenantId, "members", updated.id], updated)
      queryClient.invalidateQueries({ queryKey: [activeTenantId, "members"] })
      // If member_type changed (e.g. scout → adult), the backend removes them
      // from any patrol they were in. Invalidate all group-member caches so
      // the Groups page reflects that change without a manual reload.
      queryClient.invalidateQueries({ queryKey: [activeTenantId, "group-members"] })
    },
  })
}

export function useInviteMember() {
  const { request } = useApi()
  return useMutation({
    mutationFn: (id: string) =>
      request<{ token: string; expires_at: string }>(`/members/${id}/invite`, {
        method: "POST",
      }),
  })
}
