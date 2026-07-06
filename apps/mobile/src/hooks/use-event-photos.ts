import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useApiRequest } from "@/lib/api"
import { useActiveTenant } from "@/lib/tenant-context"
import type { EventPhoto, PhotoDownload, StorageUsage } from "@/lib/types"

/**
 * Event photos are an online surface in mobile v1 (ADR 0006): galleries are
 * bandwidth-heavy, served by short-lived presigned URLs that cannot be mirrored,
 * and browsing them at camp without signal isn't the load-bearing use case —
 * capturing is, and the upload pipeline (src/lib/photo-upload.ts) owns that.
 */

export function useEventPhotos(eventId: string | null) {
  const request = useApiRequest()
  const { activeTenant } = useActiveTenant()
  return useQuery({
    queryKey: [activeTenant?.tenant_id, "event-photos", eventId],
    queryFn: () => request<EventPhoto[]>(`/events/${eventId}/photos`),
    enabled: Boolean(activeTenant) && eventId !== null,
    retry: false,
  })
}

export function useStorageUsage() {
  const request = useApiRequest()
  const { activeTenant } = useActiveTenant()
  return useQuery({
    queryKey: [activeTenant?.tenant_id, "storage-usage"],
    queryFn: () => request<StorageUsage>("/storage/usage"),
    enabled: Boolean(activeTenant),
    retry: false,
  })
}

export function useDeletePhoto(eventId: string) {
  const request = useApiRequest()
  const { activeTenant } = useActiveTenant()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (photoId: string) => request(`/photos/${photoId}`, { method: "DELETE" }),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: [activeTenant?.tenant_id, "event-photos", eventId],
      })
      void queryClient.invalidateQueries({
        queryKey: [activeTenant?.tenant_id, "storage-usage"],
      })
    },
  })
}

/** Mint a fresh presigned GET at save time — the gallery's URLs expire quickly. */
export function useDownloadUrl() {
  const request = useApiRequest()
  return (photoId: string) => request<PhotoDownload>(`/photos/${photoId}/download`)
}
