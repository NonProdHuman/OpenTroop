"use client"

import { useMemo } from "react"
import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query"
import { useApi } from "@/lib/api"
import type { Group, GroupRoleRule, Member } from "@/types/api"

export function useGroups() {
  const { request } = useApi()
  return useQuery({
    queryKey: ["groups"],
    queryFn: () => request<Group[]>("/groups/"),
  })
}

export function useGroup(id: string | null) {
  const { request } = useApi()
  return useQuery({
    queryKey: ["groups", id],
    queryFn: () => request<Group>(`/groups/${id}`),
    enabled: id !== null,
  })
}

/** Members of a single group (resolved). Shares cache with group-level queries. */
export function useGroupMembers(groupId: string | null) {
  const { request } = useApi()
  return useQuery({
    queryKey: ["group-members", groupId],
    queryFn: () => request<Member[]>(`/groups/${groupId}/members`),
    enabled: groupId !== null,
  })
}

/** Returns a Map<groupId, memberCount> for all provided groups. */
export function useGroupMemberCounts(groups: Group[]): Map<string, number> {
  const { request } = useApi()
  const results = useQueries({
    queries: groups.map((g) => ({
      queryKey: ["group-members", g.id],
      queryFn: () => request<Member[]>(`/groups/${g.id}/members`),
    })),
  })
  return useMemo(() => {
    const map = new Map<string, number>()
    groups.forEach((g, i) => {
      const data = results[i]?.data
      if (data !== undefined) map.set(g.id, data.length)
    })
    return map
  }, [groups, results])
}

export type PatrolInfo = { id: string; name: string }

/** Returns a Map<memberId, PatrolInfo> built from all PATROL-type groups. */
export function usePatrolMemberships(): Map<string, PatrolInfo> {
  const { request } = useApi()
  const { data: groups = [] } = useGroups()

  const patrols = useMemo(() => groups.filter((g) => g.group_type === "patrol"), [groups])

  const memberResults = useQueries({
    queries: patrols.map((patrol) => ({
      queryKey: ["group-members", patrol.id],
      queryFn: () => request<Member[]>(`/groups/${patrol.id}/members`),
    })),
  })

  return useMemo(() => {
    const map = new Map<string, PatrolInfo>()
    patrols.forEach((patrol, i) => {
      const members = memberResults[i]?.data ?? []
      members.forEach((m) => map.set(m.id, { id: patrol.id, name: patrol.name }))
    })
    return map
  }, [patrols, memberResults])
}

/** Returns all groups a given member belongs to (resolved membership). */
export function useMemberGroups(memberId: string | null) {
  const { request } = useApi()
  const { data: groups = [] } = useGroups()

  const memberResults = useQueries({
    queries: groups.map((group) => ({
      queryKey: ["group-members", group.id],
      queryFn: () => request<Member[]>(`/groups/${group.id}/members`),
      enabled: memberId !== null,
    })),
  })

  return useMemo(() => {
    if (!memberId) return []
    return groups.filter((_, i) =>
      memberResults[i]?.data?.some((m) => m.id === memberId),
    )
  }, [memberId, groups, memberResults])
}

export function useCreateGroup() {
  const { request } = useApi()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: { name: string; group_type: string; color: string | null; description: string | null }) =>
      request<Group>("/groups/", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["groups"] })
    },
  })
}

export function useUpdateGroup() {
  const { request } = useApi()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<Pick<Group, "name" | "description" | "group_type" | "color">> }) =>
      request<Group>(`/groups/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
    onSuccess: (_data, { id }) => {
      queryClient.invalidateQueries({ queryKey: ["groups"] })
      queryClient.invalidateQueries({ queryKey: ["groups", id] })
    },
  })
}

export function useDeleteGroup() {
  const { request } = useApi()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => request(`/groups/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["groups"] })
    },
  })
}

export function useAddGroupMember() {
  const { request } = useApi()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ groupId, memberId }: { groupId: string; memberId: string }) =>
      request(`/groups/${groupId}/members`, {
        method: "POST",
        body: JSON.stringify({ member_id: memberId }),
      }),
    onSuccess: (_data, { groupId }) => {
      queryClient.invalidateQueries({ queryKey: ["group-members", groupId] })
    },
  })
}

export function useRemoveGroupMember() {
  const { request } = useApi()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ groupId, memberId }: { groupId: string; memberId: string }) =>
      request(`/groups/${groupId}/members/${memberId}`, { method: "DELETE" }),
    onSuccess: (_data, { groupId }) => {
      queryClient.invalidateQueries({ queryKey: ["group-members", groupId] })
    },
  })
}

// ── Role rules ───────────────────────────────────────────────────────────────

export function useGroupRoleRules(groupId: string | null) {
  const { request } = useApi()
  return useQuery({
    queryKey: ["group-role-rules", groupId],
    queryFn: () => request<GroupRoleRule[]>(`/groups/${groupId}/rules`),
    enabled: groupId !== null,
  })
}

export function useRemoveGroupRoleRule() {
  const { request } = useApi()
  const queryClient = useQueryClient()
  return useMutation({
    // Backend DELETE /groups/{id}/rules/{role_id} uses the Role's ID, not the rule row ID
    mutationFn: ({ groupId, roleId }: { groupId: string; roleId: string }) =>
      request(`/groups/${groupId}/rules/${roleId}`, { method: "DELETE" }),
    onSuccess: (_data, { groupId }) => {
      queryClient.invalidateQueries({ queryKey: ["group-role-rules", groupId] })
      queryClient.invalidateQueries({ queryKey: ["group-members", groupId] })
    },
  })
}
