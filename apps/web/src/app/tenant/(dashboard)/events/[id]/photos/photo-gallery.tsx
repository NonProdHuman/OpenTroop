"use client"

import { useState } from "react"
import Lightbox from "yet-another-react-lightbox"
import "yet-another-react-lightbox/styles.css"
import { Download, Trash2 } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { useApi } from "@/lib/api"
import { useDeletePhoto } from "@/hooks/use-event-photos"
import type { EventPhoto, PhotoDownload } from "@/types/api"

interface PhotoGalleryProps {
  eventId: string
  photos: EventPhoto[]
  isLoading: boolean
  canModerate: boolean
  currentMemberId: string | null
}

export function PhotoGallery({
  eventId,
  photos,
  isLoading,
  canModerate,
  currentMemberId,
}: PhotoGalleryProps) {
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null)
  const { request } = useApi()
  const deletePhoto = useDeletePhoto(eventId)

  if (isLoading) {
    return <div className="text-sm text-muted-foreground">Loading photos…</div>
  }
  if (photos.length === 0) {
    return (
      <div className="rounded-lg border p-8 text-center text-sm text-muted-foreground">
        No photos yet — be the first to add some.
      </div>
    )
  }

  async function handleDownload(photo: EventPhoto) {
    // Presigned GETs in the gallery list expire quickly; mint a fresh one so
    // the download link is valid at click time.
    try {
      const dl = await request<PhotoDownload>(`/photos/${photo.id}/download`)
      window.open(dl.url, "_blank", "noreferrer")
    } catch {
      toast.error("Download failed — please try again.")
    }
  }

  function handleDelete(photo: EventPhoto) {
    deletePhoto.mutate(photo.id, {
      onSuccess: () => {
        toast.success("Photo removed")
        setLightboxIndex(null)
      },
      onError: () => toast.error("Delete failed — please try again."),
    })
  }

  return (
    <>
      <ul
        data-testid="photo-grid"
        className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6"
      >
        {photos.map((photo, index) => {
          const canDelete = canModerate || photo.uploaded_by_member_id === currentMemberId
          return (
            <li key={photo.id} className="group relative" data-testid="photo-tile">
              <button
                type="button"
                className="block w-full overflow-hidden rounded-md border bg-muted focus-visible:ring-2 focus-visible:ring-ring"
                style={{ aspectRatio: "1 / 1" }}
                onClick={() => setLightboxIndex(index)}
                aria-label={photo.caption ?? "View photo"}
              >
                {/* Presigned, short-lived URL — next/image's optimizer would proxy
                    and cache it server-side, defeating both the expiry and the
                    private-bucket model, so a plain img is deliberate here. */}
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={photo.display_url}
                  alt={photo.caption ?? ""}
                  loading="lazy"
                  className="h-full w-full object-cover transition-transform group-hover:scale-105"
                />
              </button>
              <div className="absolute right-1 top-1 hidden gap-1 group-hover:flex">
                <Button
                  size="icon"
                  variant="secondary"
                  className="h-7 w-7"
                  aria-label="Download photo"
                  onClick={() => void handleDownload(photo)}
                >
                  <Download className="h-3.5 w-3.5" />
                </Button>
                {canDelete && (
                  <Button
                    size="icon"
                    variant="destructive"
                    className="h-7 w-7"
                    aria-label="Delete photo"
                    data-testid="delete-photo"
                    onClick={() => handleDelete(photo)}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                )}
              </div>
            </li>
          )
        })}
      </ul>

      <Lightbox
        open={lightboxIndex !== null}
        index={lightboxIndex ?? 0}
        close={() => setLightboxIndex(null)}
        slides={photos.map((p) => ({
          src: p.display_url,
          width: p.width,
          height: p.height,
          description: p.caption ?? undefined,
        }))}
      />
    </>
  )
}
