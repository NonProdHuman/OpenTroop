"use client"

import { useQuery } from "@tanstack/react-query"
import { useApi } from "@/lib/api"
import type { Group } from "@/types/api"

export function useGroups() {
  const { request } = useApi()
  return useQuery({
    queryKey: ["groups"],
    queryFn: () => request<Group[]>("/groups/"),
  })
}
