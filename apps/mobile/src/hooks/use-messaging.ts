import { useCallback } from "react"
import { useQuery } from "@tanstack/react-query"
import { useApiRequest } from "@/lib/api"
import { useActiveTenant } from "@/lib/tenant-context"
import type { Group, MessageCreate, MessageWithPreview } from "@/lib/types"

/**
 * Announcement compose is an online action (GH-146): the group list and the
 * send both need the network. Reads go through the sync context's authenticated
 * client; the resulting message lands in every recipient's inbox (and pushes).
 */

export function useGroupsOnline(enabled: boolean) {
  const request = useApiRequest()
  const { activeTenant } = useActiveTenant()
  return useQuery({
    queryKey: [activeTenant?.tenant_id, "groups-online"],
    queryFn: () => request<Group[]>("/groups"),
    enabled: enabled && Boolean(activeTenant),
    retry: false,
  })
}

/** Compose → send in one call (draft then send), returning the delivery preview. */
export function useComposeAndSend() {
  const request = useApiRequest()
  return useCallback(
    async (data: MessageCreate): Promise<MessageWithPreview> => {
      const created = await request<MessageWithPreview>("/messages", {
        method: "POST",
        body: data,
      })
      await request(`/messages/${created.message.id}/send`, { method: "POST" })
      return created
    },
    [request],
  )
}
