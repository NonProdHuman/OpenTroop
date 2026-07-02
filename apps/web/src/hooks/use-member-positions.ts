"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { queryKeys } from "@/lib/query-keys"
import { useApi } from "@/lib/api"
import { useActiveTenant } from "@/lib/tenant-context"
import type { MemberPositionAssignment } from "@/types/api"

export function useMemberPositions(
  memberId: string | null,
  opts: { history?: boolean } = {},
) {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  const history = opts.history ?? false
  return useQuery({
    queryKey: queryKeys.memberPositions(activeTenantId, memberId, history),
    queryFn: () =>
      request<MemberPositionAssignment[]>(
        `/members/${memberId}/positions${history ? "?current=false" : ""}`,
      ),
    enabled: memberId !== null && Boolean(activeTenantId),
  })
}

/** Invalidate everything a term change can affect: the member's terms (current +
 * history), the session permission set, and rule-driven group membership. */
function useInvalidateMemberPositions() {
  const { activeTenantId } = useActiveTenant()
  const queryClient = useQueryClient()
  return (memberId: string) => {
    queryClient.invalidateQueries({ queryKey: queryKeys.memberPositions(activeTenantId, memberId) })
    queryClient.invalidateQueries({ queryKey: queryKeys.session(activeTenantId) })
    // Position rules drive dynamic group membership (e.g. PLC) — refresh group caches.
    queryClient.invalidateQueries({ queryKey: queryKeys.groupMembers(activeTenantId) })
  }
}

export function useAssignMemberPosition() {
  const { request } = useApi()
  const invalidate = useInvalidateMemberPositions()
  return useMutation({
    mutationFn: ({
      memberId,
      positionId,
      startDate,
      endDate,
    }: {
      memberId: string
      positionId: string
      /** ISO date; backend defaults to today when omitted. */
      startDate?: string | null
      /** ISO date; set for a closed (historical) term. */
      endDate?: string | null
    }) =>
      request<MemberPositionAssignment>(`/members/${memberId}/positions`, {
        method: "POST",
        body: JSON.stringify({
          position_id: positionId,
          ...(startDate ? { start_date: startDate } : {}),
          ...(endDate ? { end_date: endDate } : {}),
        }),
      }),
    onSuccess: (_data, { memberId }) => invalidate(memberId),
  })
}

export function useUpdateMemberPositionTerm() {
  const { request } = useApi()
  const invalidate = useInvalidateMemberPositions()
  return useMutation({
    // PATCH semantics: omitted fields are untouched; `end_date: null` reopens a term.
    mutationFn: ({
      memberId,
      assignmentId,
      data,
    }: {
      memberId: string
      assignmentId: string
      data: { start_date?: string | null; end_date?: string | null }
    }) =>
      request<MemberPositionAssignment>(`/members/${memberId}/positions/${assignmentId}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    onSuccess: (_data, { memberId }) => invalidate(memberId),
  })
}

export function useRemoveMemberPosition() {
  const { request } = useApi()
  const invalidate = useInvalidateMemberPositions()
  return useMutation({
    // Terms are addressed by their own assignment id (a member can hold the same
    // position across multiple historical terms).
    mutationFn: ({ memberId, assignmentId }: { memberId: string; assignmentId: string }) =>
      request(`/members/${memberId}/positions/${assignmentId}`, { method: "DELETE" }),
    onSuccess: (_data, { memberId }) => invalidate(memberId),
  })
}
