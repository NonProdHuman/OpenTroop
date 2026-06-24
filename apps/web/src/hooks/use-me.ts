"use client"

import { useQuery } from "@tanstack/react-query"
import { useApi } from "@/lib/api"
import type { User } from "@/types/api"

/** The signed-in platform User (includes platform_role for control-plane gating). */
export function useMe() {
  const { request } = useApi()
  return useQuery({
    queryKey: ["me"],
    queryFn: () => request<User>("/auth/me"),
  })
}
