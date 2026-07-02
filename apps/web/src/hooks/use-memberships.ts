"use client"

import { useQuery } from "@tanstack/react-query"
import { queryKeys } from "@/lib/query-keys"
import { useApi } from "@/lib/api"
import type { Membership } from "@/types/api"

export function useMemberships() {
  const { request } = useApi()
  return useQuery({
    queryKey: queryKeys.memberships(),
    queryFn: () => request<Membership[]>("/auth/memberships"),
  })
}
