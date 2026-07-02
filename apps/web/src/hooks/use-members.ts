"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { queryKeys } from "@/lib/query-keys"
import { useApi } from "@/lib/api"
import { useActiveTenant } from "@/lib/tenant-context"
import type { Member } from "@/types/api"

export function useMembers() {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: queryKeys.members(activeTenantId),
    queryFn: () => request<Member[]>("/members"),
    enabled: Boolean(activeTenantId),
  })
}

export function useMember(id: string | null) {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: queryKeys.member(activeTenantId, id),
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
      request<Member>("/members", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.members(activeTenantId) })
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
      queryClient.setQueryData(queryKeys.member(activeTenantId, updated.id), updated)
      queryClient.invalidateQueries({ queryKey: queryKeys.members(activeTenantId) })
      // If member_type changed (e.g. scout → adult), the backend removes them
      // from any patrol they were in. Invalidate all group-member caches so
      // the Groups page reflects that change without a manual reload.
      queryClient.invalidateQueries({ queryKey: queryKeys.groupMembers(activeTenantId) })
    },
  })
}

export function useInviteMember() {
  const { request } = useApi()
  return useMutation({
    mutationFn: (id: string) =>
      request<{ token: string; expires_at: string; email_sent: boolean }>(
        `/members/${id}/invite`,
        { method: "POST" },
      ),
  })
}
