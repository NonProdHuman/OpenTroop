"use client"

import { useQuery } from "@tanstack/react-query"
import { useApi } from "@/lib/api"
import type { Membership } from "@/types/api"

export function useMemberships() {
  const { request } = useApi()
  return useQuery({
    queryKey: ["memberships"],
    queryFn: () => request<Membership[]>("/auth/memberships"),
  })
}
