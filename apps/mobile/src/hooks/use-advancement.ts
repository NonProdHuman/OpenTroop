import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useApiRequest } from "@/lib/api"
import { useActiveTenant } from "@/lib/tenant-context"
import type {
  AdvancementQueue,
  AdvancementScout,
  Completion,
  CompletionStatus,
  MemberAdvancement,
  MemberMeritBadge,
  MeritBadge,
  RankProgress,
  TenantSettings,
} from "@/lib/types"

/**
 * Advancement is an online surface in mobile v1 (GH-93 follow-up): the
 * catalog + progress live server-side and entries are BOR-adjacent workflow,
 * not at-camp actions — offline advancement entry graduates to the outbox
 * later if it earns its keep. Queries go through the sync context's
 * authenticated client and fail soft with an offline message.
 */

export function useAdvancementScouts() {
  const request = useApiRequest()
  const { activeTenant } = useActiveTenant()
  return useQuery({
    queryKey: [activeTenant?.tenant_id, "advancement-scouts"],
    queryFn: () => request<AdvancementScout[]>("/advancement/scouts"),
    enabled: Boolean(activeTenant),
    retry: false,
  })
}

export function useMemberAdvancement(memberId: string | null) {
  const request = useApiRequest()
  const { activeTenant } = useActiveTenant()
  return useQuery({
    queryKey: [activeTenant?.tenant_id, "member-advancement", memberId],
    queryFn: () => request<MemberAdvancement>(`/members/${memberId}/advancement`),
    enabled: Boolean(activeTenant) && memberId !== null,
    retry: false,
  })
}

export function useMeritBadgeCatalog() {
  const request = useApiRequest()
  const { activeTenant } = useActiveTenant()
  return useQuery({
    queryKey: [activeTenant?.tenant_id, "merit-badges"],
    queryFn: () => request<MeritBadge[]>("/merit-badges"),
    enabled: Boolean(activeTenant),
    retry: false,
  })
}

export function useTenantSettings() {
  const request = useApiRequest()
  const { activeTenant } = useActiveTenant()
  return useQuery({
    queryKey: [activeTenant?.tenant_id, "tenant-settings"],
    queryFn: () => request<TenantSettings>("/tenant/settings"),
    enabled: Boolean(activeTenant),
    retry: false,
  })
}

/** The tenant's pending-approval queue (reported completions + merit badges). */
export function useAdvancementQueue(enabled = true) {
  const request = useApiRequest()
  const { activeTenant } = useActiveTenant()
  return useQuery({
    queryKey: [activeTenant?.tenant_id, "advancement-queue"],
    queryFn: () => request<AdvancementQueue>("/advancement/queue"),
    enabled: enabled && Boolean(activeTenant),
    retry: false,
  })
}

/**
 * Invalidate everything a completion/badge/rank write can move. When a member id
 * is known we scope the member-advancement invalidation; otherwise (PATCH/DELETE
 * by completion/badge id) we invalidate the whole member-advancement prefix. The
 * approval queue is always refreshed.
 */
function useInvalidateAdvancement() {
  const queryClient = useQueryClient()
  const { activeTenant } = useActiveTenant()
  const tenantId = activeTenant?.tenant_id
  return (memberId?: string) => {
    queryClient.invalidateQueries({
      queryKey: memberId
        ? [tenantId, "member-advancement", memberId]
        : [tenantId, "member-advancement"],
    })
    queryClient.invalidateQueries({ queryKey: [tenantId, "advancement-queue"] })
  }
}

export function useRecordCompletion(memberId: string) {
  const request = useApiRequest()
  const invalidate = useInvalidateAdvancement()
  return useMutation({
    mutationFn: (data: { requirement_id: string; date_completed: string; note?: string }) =>
      request<Completion>(`/members/${memberId}/advancement/completions`, {
        method: "POST",
        body: data,
      }),
    onSuccess: () => invalidate(memberId),
  })
}

/** Approve / reject (status) or correct the date/note of an existing completion. */
export function useUpdateCompletion() {
  const request = useApiRequest()
  const invalidate = useInvalidateAdvancement()
  return useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: string
      data: { status?: CompletionStatus; date_completed?: string; note?: string | null }
    }) => request<Completion>(`/advancement/completions/${id}`, { method: "PATCH", body: data }),
    onSuccess: () => invalidate(),
  })
}

/** Revoke (soft-delete) a completion. */
export function useRevokeCompletion() {
  const request = useApiRequest()
  const invalidate = useInvalidateAdvancement()
  return useMutation({
    mutationFn: (id: string) =>
      request(`/advancement/completions/${id}`, { method: "DELETE" }),
    onSuccess: () => invalidate(),
  })
}

export function useRecordMeritBadge(memberId: string) {
  const request = useApiRequest()
  const invalidate = useInvalidateAdvancement()
  return useMutation({
    mutationFn: (data: { merit_badge_id: string; date_completed?: string }) =>
      request<MemberMeritBadge>(`/members/${memberId}/merit-badges`, {
        method: "POST",
        body: data,
      }),
    onSuccess: () => invalidate(memberId),
  })
}

/** Edit a member's merit badge (completion date / status). */
export function useUpdateMeritBadge() {
  const request = useApiRequest()
  const invalidate = useInvalidateAdvancement()
  return useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: string
      data: { status?: CompletionStatus; date_completed?: string | null }
    }) => request<MemberMeritBadge>(`/advancement/merit-badges/${id}`, { method: "PATCH", body: data }),
    onSuccess: () => invalidate(),
  })
}

/** Set/clear a rank's BOR (completed) and awarded dates. */
export function useUpdateRankProgress(memberId: string) {
  const request = useApiRequest()
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
        body: data,
      }),
    onSuccess: () => invalidate(memberId),
  })
}
