"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useApi } from "@/lib/api"
import type { Member } from "@/types/api"

export function useMembers() {
  const { request } = useApi()
  return useQuery({
    queryKey: ["members"],
    queryFn: () => request<Member[]>("/members/"),
  })
}

export function useMember(id: string | null) {
  const { request } = useApi()
  return useQuery({
    queryKey: ["members", id],
    queryFn: () => request<Member>(`/members/${id}`),
    enabled: id !== null,
  })
}

export function useUpdateMember() {
  const { request } = useApi()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<Member> }) =>
      request<Member>(`/members/${id}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    onSuccess: (updated) => {
      queryClient.setQueryData(["members", updated.id], updated)
      queryClient.invalidateQueries({ queryKey: ["members"] })
    },
  })
}

export function useInviteMember() {
  const { request } = useApi()
  return useMutation({
    mutationFn: (id: string) =>
      request<{ token: string; expires_at: string }>(`/members/${id}/invite`, {
        method: "POST",
      }),
  })
}
