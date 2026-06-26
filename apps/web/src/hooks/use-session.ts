"use client"

import { useQuery } from "@tanstack/react-query"
import { useApi } from "@/lib/api"
import type { Permission, Session } from "@/types/api"

const TENANT_ID = process.env.NEXT_PUBLIC_TENANT_ID ?? ""

export function useSession() {
  const { request } = useApi()
  return useQuery({
    queryKey: ["session", TENANT_ID],
    queryFn: () => request<Session>("/auth/session"),
  })
}

export function usePermissions() {
  const { data, isLoading } = useSession()
  const set = new Set(data?.permissions ?? [])
  return {
    has: (p: Permission) => set.has(p),
    isMember: data?.member != null,
    isLoading,
  }
}
