"use client"

import { useCallback, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { queryKeys } from "@/lib/query-keys"
import { useApi } from "@/lib/api"
import { useActiveTenant } from "@/lib/tenant-context"
import { isSupportedImage, processPhoto } from "@/lib/image-processing"
import type { EventPhoto, PhotoInitiateResponse, StorageUsage } from "@/types/api"

export function useEventPhotos(eventId: string | null) {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: queryKeys.eventPhotos(activeTenantId, eventId),
    queryFn: () => request<EventPhoto[]>(`/events/${eventId}/photos`),
    enabled: eventId !== null && Boolean(activeTenantId),
  })
}

export function useStorageUsage() {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: queryKeys.storageUsage(activeTenantId),
    queryFn: () => request<StorageUsage>("/storage/usage"),
    enabled: Boolean(activeTenantId),
  })
}

export function useDeletePhoto(eventId: string) {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (photoId: string) => request(`/photos/${photoId}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.eventPhotos(activeTenantId, eventId) })
      queryClient.invalidateQueries({ queryKey: queryKeys.storageUsage(activeTenantId) })
    },
  })
}

export function useUpdatePhotoCaption(eventId: string) {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ photoId, caption }: { photoId: string; caption: string | null }) =>
      request<EventPhoto>(`/photos/${photoId}`, {
        method: "PATCH",
        body: JSON.stringify({ caption }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.eventPhotos(activeTenantId, eventId) })
    },
  })
}

export type UploadItemStatus = "processing" | "uploading" | "done" | "error" | "skipped"

export interface UploadItem {
  name: string
  status: UploadItemStatus
  error?: string
}

/**
 * The full upload pipeline for a batch of picked files (GH-145 spec §4):
 * downscale + EXIF-strip in the browser → `initiate` (quota reservation +
 * presigned PUTs) → PUT the bytes straight to object storage (never through
 * the API) → `complete` each photo (server HEAD-verifies and settles quota).
 *
 * Files upload sequentially — parents on hotel Wi-Fi beat parallel stalls —
 * with per-file status surfaced through `items` for the progress list.
 */
export function useUploadPhotos(eventId: string) {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  const queryClient = useQueryClient()
  const [items, setItems] = useState<UploadItem[]>([])
  const [isUploading, setIsUploading] = useState(false)

  const setItem = useCallback((index: number, patch: Partial<UploadItem>) => {
    setItems((prev) => prev.map((it, i) => (i === index ? { ...it, ...patch } : it)))
  }, [])

  const upload = useCallback(
    async (files: File[]) => {
      if (files.length === 0 || isUploading) return
      setIsUploading(true)
      setItems(files.map((f) => ({ name: f.name, status: "processing" as const })))
      let uploaded = 0
      try {
        for (const [index, file] of files.entries()) {
          if (!isSupportedImage(file)) {
            setItem(index, { status: "skipped", error: "Not a supported image type" })
            continue
          }
          try {
            const processed = await processPhoto(file)
            const initiated = await request<PhotoInitiateResponse>(
              `/events/${eventId}/photos/initiate`,
              {
                method: "POST",
                body: JSON.stringify({
                  photos: [
                    {
                      content_type: processed.contentType,
                      byte_length: processed.blob.size,
                      width: processed.width,
                      height: processed.height,
                    },
                  ],
                }),
              },
            )
            const target = initiated.uploads[0]
            setItem(index, { status: "uploading" })
            // Direct-to-bucket presigned PUT — a plain fetch, no auth headers.
            const put = await fetch(target.upload_url, {
              method: "PUT",
              headers: { "Content-Type": processed.contentType },
              body: processed.blob,
            })
            if (!put.ok) throw new Error(`Storage upload failed (${put.status})`)
            await request(`/photos/${target.photo_id}/complete`, { method: "POST" })
            setItem(index, { status: "done" })
            uploaded += 1
          } catch (error) {
            setItem(index, {
              status: "error",
              error: error instanceof Error ? error.message : "Upload failed",
            })
          }
        }
      } finally {
        setIsUploading(false)
        if (uploaded > 0) {
          queryClient.invalidateQueries({
            queryKey: queryKeys.eventPhotos(activeTenantId, eventId),
          })
          queryClient.invalidateQueries({ queryKey: queryKeys.storageUsage(activeTenantId) })
        }
      }
    },
    [activeTenantId, eventId, isUploading, queryClient, request, setItem],
  )

  const reset = useCallback(() => setItems([]), [])

  return { upload, items, isUploading, reset }
}
