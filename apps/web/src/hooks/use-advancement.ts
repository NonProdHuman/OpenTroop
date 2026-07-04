"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { queryKeys } from "@/lib/query-keys"
import { useApi } from "@/lib/api"
import { useActiveTenant } from "@/lib/tenant-context"
import type {
  AdvancementQueue,
  Completion,
  CompletionStatus,
  MemberAdvancement,
  MemberMeritBadge,
  MeritBadge,
  RankProgress,
  RankWithSets,
} from "@/types/api"

export function useAdvancementRanks() {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: queryKeys.advancementRanks(activeTenantId),
    queryFn: () => request<RankWithSets[]>("/advancement/ranks"),
    enabled: Boolean(activeTenantId),
  })
}

export function useMeritBadges() {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: queryKeys.meritBadges(activeTenantId),
    queryFn: () => request<MeritBadge[]>("/merit-badges"),
    enabled: Boolean(activeTenantId),
  })
}

export function useMemberAdvancement(memberId: string | null) {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: queryKeys.memberAdvancement(activeTenantId, memberId),
    queryFn: () => request<MemberAdvancement>(`/members/${memberId}/advancement`),
    enabled: memberId !== null && Boolean(activeTenantId),
  })
}

export function useAdvancementQueue(enabled = true) {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: queryKeys.advancementQueue(activeTenantId),
    queryFn: () => request<AdvancementQueue>("/advancement/queue"),
    enabled: enabled && Boolean(activeTenantId),
  })
}

/** Invalidate everything a completion/badge write can move. */
function useInvalidateAdvancement() {
  const queryClient = useQueryClient()
  const { activeTenantId } = useActiveTenant()
  return (memberId?: string) => {
    if (memberId) {
      queryClient.invalidateQueries({
        queryKey: queryKeys.memberAdvancement(activeTenantId, memberId),
      })
    } else {
      queryClient.invalidateQueries({ queryKey: [activeTenantId, "member-advancement"] })
    }
    queryClient.invalidateQueries({ queryKey: queryKeys.advancementQueue(activeTenantId) })
  }
}

export function useCreateCompletion(memberId: string) {
  const { request } = useApi()
  const invalidate = useInvalidateAdvancement()
  return useMutation({
    mutationFn: (body: { requirement_id: string; date_completed: string; note?: string | null }) =>
      request<Completion>(`/members/${memberId}/advancement/completions`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => invalidate(memberId),
  })
}

export function useUpdateCompletion() {
  const { request } = useApi()
  const invalidate = useInvalidateAdvancement()
  return useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: string
      data: { status?: CompletionStatus; date_completed?: string; note?: string | null }
    }) =>
      request<Completion>(`/advancement/completions/${id}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    onSuccess: () => invalidate(),
  })
}

export function useRevokeCompletion() {
  const { request } = useApi()
  const invalidate = useInvalidateAdvancement()
  return useMutation({
    mutationFn: (id: string) =>
      request(`/advancement/completions/${id}`, { method: "DELETE" }),
    onSuccess: () => invalidate(),
  })
}

export function useCreateMemberMeritBadge(memberId: string) {
  const { request } = useApi()
  const invalidate = useInvalidateAdvancement()
  return useMutation({
    mutationFn: (body: {
      merit_badge_id: string
      date_started?: string | null
      date_completed?: string | null
      counselor_name?: string | null
    }) =>
      request<MemberMeritBadge>(`/members/${memberId}/merit-badges`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => invalidate(memberId),
  })
}

export function useUpdateMemberMeritBadge() {
  const { request } = useApi()
  const invalidate = useInvalidateAdvancement()
  return useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: string
      data: {
        status?: CompletionStatus
        date_started?: string | null
        date_completed?: string | null
        counselor_name?: string | null
      }
    }) =>
      request<MemberMeritBadge>(`/advancement/merit-badges/${id}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    onSuccess: () => invalidate(),
  })
}

export function useUpdateRankProgress(memberId: string) {
  const { request } = useApi()
  const invalidate = useInvalidateAdvancement()
  return useMutation({
    mutationFn: ({
      rankId,
      data,
    }: {
      rankId: string
      data: { completed_date?: string | null; awarded_date?: string | null }
    }) =>
      request<RankProgress>(`/members/${memberId}/advancement/ranks/${rankId}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    onSuccess: () => invalidate(memberId),
  })
}
