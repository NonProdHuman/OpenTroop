"use client"

import { useQuery } from "@tanstack/react-query"
import { useApi } from "@/lib/api"
import { useActiveTenant } from "@/lib/tenant-context"
import type { MemberRoleAssignment } from "@/types/api"

export function useRoleAssignments() {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: [activeTenantId, "role-assignments"],
    queryFn: () => request<MemberRoleAssignment[]>("/role-assignments/"),
    enabled: Boolean(activeTenantId),
  })
}

export function useMemberRoleAssignments(memberId: string | null) {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: [activeTenantId, "role-assignments", memberId],
    queryFn: () =>
      request<MemberRoleAssignment[]>(`/role-assignments/?member_id=${memberId}`),
    enabled: memberId !== null && Boolean(activeTenantId),
  })
}
