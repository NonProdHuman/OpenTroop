"use client"

import { useQuery } from "@tanstack/react-query"
import { useApi } from "@/lib/api"
import type { Role } from "@/types/api"

export function useRoles() {
  const { request } = useApi()
  return useQuery({
    queryKey: ["roles"],
    queryFn: () => request<Role[]>("/roles/"),
  })
}
