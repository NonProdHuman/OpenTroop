"use client"

import { useQuery } from "@tanstack/react-query"
import { useApi } from "@/lib/api"
import { useActiveTenant } from "@/lib/tenant-context"
import type { Position } from "@/types/api"

export function usePositions() {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: [activeTenantId, "positions"],
    queryFn: () => request<Position[]>("/positions/"),
    enabled: Boolean(activeTenantId),
  })
}
