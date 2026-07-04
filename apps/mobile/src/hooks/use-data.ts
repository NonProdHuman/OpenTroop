import { useQuery } from "@tanstack/react-query"
import { useApi, useAuthApi } from "@/lib/api"
import { useActiveTenant } from "@/lib/tenant-context"
import type { Event, Member, Membership } from "@/lib/types"

/**
 * M3 online-read hooks. Query keys are tenant-prefixed (same convention as the
 * web app) so switching troops never serves another troop's cache. The M4 data
 * layer replaces the fetchers with local-mirror reads — the components keep
 * these hook signatures.
 */

export function useMemberships() {
  const { request } = useAuthApi()
  return useQuery({
    queryKey: ["memberships"],
    queryFn: () => request<Membership[]>("/auth/memberships"),
  })
}

export function useMembers() {
  const { request } = useApi()
  const { activeTenant } = useActiveTenant()
  return useQuery({
    queryKey: [activeTenant?.tenant_id, "members"],
    queryFn: () => request<Member[]>("/members"),
    enabled: Boolean(activeTenant),
  })
}

export function useEvents() {
  const { request } = useApi()
  const { activeTenant } = useActiveTenant()
  return useQuery({
    queryKey: [activeTenant?.tenant_id, "events"],
    queryFn: () => request<Event[]>("/events"),
    enabled: Boolean(activeTenant),
  })
}
