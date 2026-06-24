"use client"

import { useQuery } from "@tanstack/react-query"
import { useApi } from "@/lib/api"
import type { Patrol } from "@/types/api"

export function usePatrols() {
  const { request } = useApi()
  return useQuery({
    queryKey: ["patrols"],
    queryFn: () => request<Patrol[]>("/patrols/"),
  })
}
