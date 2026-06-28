import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useApi } from "@/lib/api"
import type { Member } from "@/types/api"

export function useClaimMembership() {
  const { request } = useApi()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (token: string) => {
      return request<Member>("/auth/claim", {
        method: "POST",
        body: JSON.stringify({ token }),
      })
    },
    onSuccess: () => {
      // Invalidate memberships so the new tenant appears in the TenantSwitcher immediately
      queryClient.invalidateQueries({ queryKey: ["memberships"] })
    },
  })
}
