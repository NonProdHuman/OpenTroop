"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { queryKeys } from "@/lib/query-keys"
import { useApi } from "@/lib/api"
import { useActiveTenant } from "@/lib/tenant-context"
import type { MemberRelationship, RelationshipType } from "@/types/api"

export function useRelationships(memberId: string | null) {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: queryKeys.relationships(activeTenantId, memberId),
    queryFn: () =>
      request<MemberRelationship[]>(`/relationships?member_id=${memberId}`),
    enabled: memberId !== null && Boolean(activeTenantId),
  })
}

export function useCreateRelationship() {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: {
      from_member_id: string
      to_member_id: string
      relationship_type: RelationshipType
    }) =>
      request<MemberRelationship>("/relationships", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.relationships(activeTenantId, variables.from_member_id),
      })
      queryClient.invalidateQueries({
        queryKey: queryKeys.relationships(activeTenantId, variables.to_member_id),
      })
    },
  })
}

export function useDeleteRelationship() {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      relId,
    }: {
      relId: string
      memberId: string
    }) =>
      request<void>(`/relationships/${relId}`, { method: "DELETE" }),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.relationships(activeTenantId, variables.memberId),
      })
    },
  })
}
