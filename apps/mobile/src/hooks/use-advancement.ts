import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useSyncContext } from "@/lib/sync-context"
import { useActiveTenant } from "@/lib/tenant-context"
import type { AdvancementScout, MemberAdvancement, MeritBadge, TenantSettings } from "@/lib/types"

/**
 * Advancement is an online surface in mobile v1 (GH-93 follow-up): the
 * catalog + progress live server-side and entries are BOR-adjacent workflow,
 * not at-camp actions — offline advancement entry graduates to the outbox
 * later if it earns its keep. Queries go through the sync context's
 * authenticated client and fail soft with an offline message.
 */

function useRequest() {
  const { http } = useSyncContext()
  return async <T>(path: string, init?: { method: string; body?: unknown }): Promise<T> => {
    if (!http) throw new Error("No active troop")
    const response = await http(path, init ?? { method: "GET" })
    if (response.status >= 400) {
      const detail =
        response.body && typeof response.body === "object" && "detail" in response.body
          ? String((response.body as { detail: unknown }).detail)
          : `HTTP ${response.status}`
      throw new Error(detail)
    }
    return response.body as T
  }
}

export function useAdvancementScouts() {
  const request = useRequest()
  const { activeTenant } = useActiveTenant()
  return useQuery({
    queryKey: [activeTenant?.tenant_id, "advancement-scouts"],
    queryFn: () => request<AdvancementScout[]>("/advancement/scouts"),
    enabled: Boolean(activeTenant),
    retry: false,
  })
}

export function useMemberAdvancement(memberId: string | null) {
  const request = useRequest()
  const { activeTenant } = useActiveTenant()
  return useQuery({
    queryKey: [activeTenant?.tenant_id, "member-advancement", memberId],
    queryFn: () => request<MemberAdvancement>(`/members/${memberId}/advancement`),
    enabled: Boolean(activeTenant) && memberId !== null,
    retry: false,
  })
}

export function useMeritBadgeCatalog() {
  const request = useRequest()
  const { activeTenant } = useActiveTenant()
  return useQuery({
    queryKey: [activeTenant?.tenant_id, "merit-badges"],
    queryFn: () => request<MeritBadge[]>("/merit-badges"),
    enabled: Boolean(activeTenant),
    retry: false,
  })
}

export function useTenantSettings() {
  const request = useRequest()
  const { activeTenant } = useActiveTenant()
  return useQuery({
    queryKey: [activeTenant?.tenant_id, "tenant-settings"],
    queryFn: () => request<TenantSettings>("/tenant/settings"),
    enabled: Boolean(activeTenant),
    retry: false,
  })
}

export function useRecordCompletion(memberId: string) {
  const request = useRequest()
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
  const request = useRequest()
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
