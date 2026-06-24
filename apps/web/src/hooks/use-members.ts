"use client"

import { useQuery } from "@tanstack/react-query"
import { useApi } from "@/lib/api"
import type { Member } from "@/types/api"

export function useMembers() {
  const { request } = useApi()
  return useQuery({
    queryKey: ["members"],
    queryFn: () => request<Member[]>("/members/"),
  })
}
