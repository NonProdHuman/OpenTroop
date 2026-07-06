import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useApiRequest } from "@/lib/api"
import { useActiveTenant } from "@/lib/tenant-context"
import type { AdvancementScout, MemberAdvancement, MeritBadge, TenantSettings } from "@/lib/types"

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

export function useRecordCompletion(memberId: string) {
  const request = useApiRequest()
  const queryClient = useQueryClient()
  const { activeTenant } = useActiveTenant()
  return useMutation({
    mutationFn: (data: { requirement_id: string; date_completed: string }) =>
      request(`/members/${memberId}/advancement/completions`, { method: "POST", body: data }),
    onSuccess: () =>
      queryClient.invalidateQueries({
        queryKey: [activeTenant?.tenant_id, "member-advancement", memberId],
      }),
  })
}

export function useRecordMeritBadge(memberId: string) {
  const request = useApiRequest()
  const queryClient = useQueryClient()
  const { activeTenant } = useActiveTenant()
  return useMutation({
    mutationFn: (data: { merit_badge_id: string; date_completed: string }) =>
      request(`/members/${memberId}/merit-badges`, { method: "POST", body: data }),
    onSuccess: () =>
      queryClient.invalidateQueries({
        queryKey: [activeTenant?.tenant_id, "member-advancement", memberId],
      }),
  })
}
