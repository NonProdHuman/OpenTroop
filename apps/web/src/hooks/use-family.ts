"use client"

import { useQuery } from "@tanstack/react-query"
import { queryKeys } from "@/lib/query-keys"
import { useApi } from "@/lib/api"
import { useActiveTenant } from "@/lib/tenant-context"
import type { Family } from "@/types/api"

/**
 * The caller's household for the "My Family" page (GH-143).
 *
 * `GET /members/me/family` returns `{ members, relationships }` scoped to the
 * caller's household (`{self} ∪ children/wards ∪ co-parents`). Any authenticated
 * member may call it — no `member:read` needed — and the medical bundle is
 * intact on these rows (the household is the redaction exemption). A scout or an
 * edge-less adult gets just themselves.
 */
export function useFamily() {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: queryKeys.family(activeTenantId),
    queryFn: () => request<Family>("/members/me/family"),
    enabled: Boolean(activeTenantId),
  })
}
