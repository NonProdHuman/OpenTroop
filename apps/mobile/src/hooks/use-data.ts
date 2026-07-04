import { useQuery } from "@tanstack/react-query"
import { useAuthApi } from "@/lib/api"
import type { Membership } from "@/lib/types"

/** The troop switcher's source — tenant-less, so it stays an online read. */
export function useMemberships() {
  const { request } = useAuthApi()
  return useQuery({
    queryKey: ["memberships"],
    queryFn: () => request<Membership[]>("/auth/memberships"),
  })
}
