"use client"

import { useMemo } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useApi } from "@/lib/api"
import { useActiveTenant } from "@/lib/tenant-context"
import type { Group, GroupMemberRow, GroupRosterEntry, GroupRule, Member } from "@/types/api"

export function useGroups() {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: [activeTenantId, "groups"],
    queryFn: () => request<Group[]>("/groups"),
    enabled: Boolean(activeTenantId),
  })
}

export function useGroup(id: string | null) {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: [activeTenantId, "groups", id],
    queryFn: () => request<Group>(`/groups/${id}`),
    enabled: id !== null && Boolean(activeTenantId),
  })
}

/** Members of a single group (resolved). Shares cache with group-level queries. */
export function useGroupMembers(groupId: string | null) {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: [activeTenantId, "group-members", groupId],
    queryFn: () => request<Member[]>(`/groups/${groupId}/members`),
    enabled: groupId !== null && Boolean(activeTenantId),
  })
}

/** Explicit (manual) membership rows for a group — excludes rule-derived members. */
export function useGroupManualMembers(groupId: string | null) {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: [activeTenantId, "group-manual-members", groupId],
    queryFn: () => request<GroupMemberRow[]>(`/groups/${groupId}/manual-members`),
    enabled: groupId !== null && Boolean(activeTenantId),
  })
}

/**
 * Resolved membership for every group in one request — `[{group_id, member_ids}]`.
 *
 * Backing query for the membership *selector* hooks below (`useGroupMemberCounts`,
 * `usePatrolMemberships`, `useMemberGroups`, `useGroupMemberships`), which used to fire
 * one `/groups/{id}/members` request per group and join client-side. The backend already
 * computes each group's resolved set, so a single `/groups/roster` call replaces the N+1.
 */
export function useGroupRoster() {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: [activeTenantId, "group-roster"],
    queryFn: () => request<GroupRosterEntry[]>("/groups/roster"),
    enabled: Boolean(activeTenantId),
  })
}

/** Returns a Map<groupId, memberCount> for all provided groups. */
export function useGroupMemberCounts(groups: Group[]): Map<string, number> {
  const { data: roster = [] } = useGroupRoster()
  return useMemo(() => {
    const counts = new Map(roster.map((e) => [e.group_id, e.member_ids.length]))
    const map = new Map<string, number>()
    for (const g of groups) {
      const count = counts.get(g.id)
      if (count !== undefined) map.set(g.id, count)
    }
    return map
  }, [groups, roster])
}

export type PatrolInfo = { id: string; name: string }

/** Returns a Map<memberId, PatrolInfo> built from all PATROL-type groups. */
export function usePatrolMemberships(): Map<string, PatrolInfo> {
  const { data: groups = [] } = useGroups()
  const { data: roster = [] } = useGroupRoster()

  return useMemo(() => {
    const memberIdsByGroup = new Map(roster.map((e) => [e.group_id, e.member_ids]))
    const map = new Map<string, PatrolInfo>()
    for (const patrol of groups.filter((g) => g.group_type === "patrol")) {
      for (const memberId of memberIdsByGroup.get(patrol.id) ?? []) {
        map.set(memberId, { id: patrol.id, name: patrol.name })
      }
    }
    return map
  }, [groups, roster])
}

/** Returns all groups a given member belongs to (resolved membership). */
export function useMemberGroups(memberId: string | null): Group[] {
  const { data: groups = [] } = useGroups()
  const { data: roster = [] } = useGroupRoster()

  return useMemo(() => {
    if (!memberId) return []
    const memberGroupIds = new Set(
      roster.filter((e) => e.member_ids.includes(memberId)).map((e) => e.group_id),
    )
    return groups.filter((g) => memberGroupIds.has(g.id))
  }, [memberId, groups, roster])
}

/** Returns a Map<memberId, Group[]> built from all active groups. */
export function useGroupMemberships(): Map<string, Group[]> {
  const { data: groups = [] } = useGroups()
  const { data: roster = [] } = useGroupRoster()

  return useMemo(() => {
    const groupById = new Map(groups.map((g) => [g.id, g]))
    const map = new Map<string, Group[]>()
    for (const entry of roster) {
      const group = groupById.get(entry.group_id)
      if (group === undefined) continue
      for (const memberId of entry.member_ids) {
        const existing = map.get(memberId) ?? []
        existing.push(group)
        map.set(memberId, existing)
      }
    }
    return map
  }, [groups, roster])
}


export function useCreateGroup() {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: { name: string; group_type: string; color: string | null; description: string | null; rule_logic?: string; include_parents?: boolean; cc_parents_on_messages?: boolean }) =>
      request<Group>("/groups", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [activeTenantId, "groups"] })
      queryClient.invalidateQueries({ queryKey: [activeTenantId, "group-roster"] })
    },
  })
}

export function useUpdateGroup() {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<Pick<Group, "name" | "description" | "group_type" | "color" | "rule_logic" | "include_parents" | "cc_parents_on_messages">> }) =>
      request<Group>(`/groups/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
    onSuccess: (_data, { id }) => {
      queryClient.invalidateQueries({ queryKey: [activeTenantId, "groups"] })
      queryClient.invalidateQueries({ queryKey: [activeTenantId, "groups", id] })
      // rule_logic and include_parents change resolved membership — refresh all
      // group-member caches (and everything derived from them: counts, rosters).
      queryClient.invalidateQueries({ queryKey: [activeTenantId, "group-members"] })
      queryClient.invalidateQueries({ queryKey: [activeTenantId, "group-roster"] })
    },
  })
}

export function useDeleteGroup() {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => request(`/groups/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [activeTenantId, "groups"] })
      queryClient.invalidateQueries({ queryKey: [activeTenantId, "group-roster"] })
    },
  })
}

export function useAddGroupMember() {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ groupId, memberId }: { groupId: string; memberId: string }) =>
      request(`/groups/${groupId}/members`, {
        method: "POST",
        body: JSON.stringify({ member_id: memberId }),
      }),
    onSuccess: () => {
      // Invalidate ALL group-member caches: the backend may silently remove
      // the member from a previous patrol, so every cached list could be stale.
      queryClient.invalidateQueries({ queryKey: [activeTenantId, "group-members"] })
      queryClient.invalidateQueries({ queryKey: [activeTenantId, "group-roster"] })
      queryClient.invalidateQueries({ queryKey: [activeTenantId, "group-manual-members"] })
    },
  })
}

export function useRemoveGroupMember() {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ groupId, memberId }: { groupId: string; memberId: string }) =>
      request(`/groups/${groupId}/members/${memberId}`, { method: "DELETE" }),
    onSuccess: () => {
      // Invalidate ALL group-member caches for consistency.
      queryClient.invalidateQueries({ queryKey: [activeTenantId, "group-members"] })
      queryClient.invalidateQueries({ queryKey: [activeTenantId, "group-roster"] })
      queryClient.invalidateQueries({ queryKey: [activeTenantId, "group-manual-members"] })
    },
  })
}

// ── Group rules ──────────────────────────────────────────────────────────────

export function useGroupRules(groupId: string | null) {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: [activeTenantId, "group-rules", groupId],
    queryFn: () => request<GroupRule[]>(`/groups/${groupId}/rules`),
    enabled: groupId !== null && Boolean(activeTenantId),
  })
}

export function useUpsertGroupRule() {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ groupId, dimension, values }: { groupId: string; dimension: string; values: string[] | null }) =>
      request<GroupRule>(`/groups/${groupId}/rules/${dimension}`, {
        method: "PUT",
        body: JSON.stringify({ values }),
      }),
    onSuccess: (_data, { groupId }) => {
      queryClient.invalidateQueries({ queryKey: [activeTenantId, "group-rules", groupId] })
      // Broad: other groups can depend on this one via group_member / parents-of rules.
      queryClient.invalidateQueries({ queryKey: [activeTenantId, "group-members"] })
      queryClient.invalidateQueries({ queryKey: [activeTenantId, "group-roster"] })
    },
  })
}

export function useDeleteGroupRule() {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ groupId, dimension }: { groupId: string; dimension: string }) =>
      request(`/groups/${groupId}/rules/${dimension}`, { method: "DELETE" }),
    onSuccess: (_data, { groupId }) => {
      queryClient.invalidateQueries({ queryKey: [activeTenantId, "group-rules", groupId] })
      // Broad: other groups can depend on this one via group_member / parents-of rules.
      queryClient.invalidateQueries({ queryKey: [activeTenantId, "group-members"] })
      queryClient.invalidateQueries({ queryKey: [activeTenantId, "group-roster"] })
    },
  })
}
