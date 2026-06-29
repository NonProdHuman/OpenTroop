"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useApi } from "@/lib/api"
import { useActiveTenant } from "@/lib/tenant-context"
import type { MemberPositionAssignment } from "@/types/api"

export function useMemberPositions(memberId: string | null) {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: [activeTenantId, "member-positions", memberId],
    queryFn: () => request<MemberPositionAssignment[]>(`/members/${memberId}/positions`),
    enabled: memberId !== null && Boolean(activeTenantId),
  })
}

export function useAssignMemberPosition() {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ memberId, positionId }: { memberId: string; positionId: string }) =>
      request<MemberPositionAssignment>(`/members/${memberId}/positions`, {
        method: "POST",
        body: JSON.stringify({ position_id: positionId }),
      }),
    onSuccess: (_data, { memberId }) => {
      queryClient.invalidateQueries({ queryKey: [activeTenantId, "member-positions", memberId] })
      queryClient.invalidateQueries({ queryKey: [activeTenantId, "session"] })
      // Position rules drive dynamic group membership (e.g. PLC) — refresh group caches.
      queryClient.invalidateQueries({ queryKey: [activeTenantId, "group-members"] })
    },
  })
}

export function useRemoveMemberPosition() {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ memberId, positionId }: { memberId: string; positionId: string }) =>
      request(`/members/${memberId}/positions/${positionId}`, { method: "DELETE" }),
    onSuccess: (_data, { memberId }) => {
      queryClient.invalidateQueries({ queryKey: [activeTenantId, "member-positions", memberId] })
      queryClient.invalidateQueries({ queryKey: [activeTenantId, "session"] })
      // Position rules drive dynamic group membership (e.g. PLC) — refresh group caches.
      queryClient.invalidateQueries({ queryKey: [activeTenantId, "group-members"] })
    },
  })
}
