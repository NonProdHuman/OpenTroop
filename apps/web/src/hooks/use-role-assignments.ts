"use client"

import { useQuery } from "@tanstack/react-query"
import { useApi } from "@/lib/api"
import type { MemberRoleAssignment } from "@/types/api"

export function useRoleAssignments() {
  const { request } = useApi()
  return useQuery({
    queryKey: ["role-assignments"],
    queryFn: () => request<MemberRoleAssignment[]>("/role-assignments/"),
  })
}

export function useMemberRoleAssignments(memberId: string | null) {
  const { request } = useApi()
  return useQuery({
    queryKey: ["role-assignments", memberId],
    queryFn: () =>
      request<MemberRoleAssignment[]>(`/role-assignments/?member_id=${memberId}`),
    enabled: memberId !== null,
  })
}
