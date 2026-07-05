import { useCallback } from "react"
import { useQuery } from "@tanstack/react-query"
import { useSyncContext } from "@/lib/sync-context"
import { useActiveTenant } from "@/lib/tenant-context"
import type { Group, MessageCreate, MessageWithPreview } from "@/lib/types"

/**
 * Announcement compose is an online action (GH-146): the group list and the
 * send both need the network. Reads go through the sync context's authenticated
 * client; the resulting message lands in every recipient's inbox (and pushes).
 */

function useRequest() {
  const { http } = useSyncContext()
  return useCallback(
    async <T>(path: string, init?: { method: string; body?: unknown }): Promise<T> => {
      if (!http) throw new Error("No active troop")
      const response = await http(path, init ?? { method: "GET" })
      if (response.status >= 400) {
        const detail =
          response.body && typeof response.body === "object" && "detail" in response.body
            ? String((response.body as { detail: unknown }).detail)
            : `HTTP ${response.status}`
        throw new Error(detail)
      }
      return response.body as T
    },
    [http],
  )
}

export function useGroupsOnline(enabled: boolean) {
  const request = useRequest()
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
  const request = useRequest()
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
