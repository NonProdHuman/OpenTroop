"use client"

import Link from "next/link"
import { useParams } from "next/navigation"
import { ArrowLeft } from "lucide-react"
import { PageHeader } from "@/components/page-header"
import { buttonVariants } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { useEvent } from "@/hooks/use-events"
import { useEventPhotos } from "@/hooks/use-event-photos"
import { usePermissions, useSession } from "@/hooks/use-session"
import { PhotoGallery } from "./photo-gallery"
import { PhotoUploader } from "./photo-uploader"

export default function EventPhotosPage() {
  const { id } = useParams<{ id: string }>()
  const { has, isLoading: permsLoading } = usePermissions()
  const { data: session } = useSession()
  const { data: event, isLoading: eventLoading, isError } = useEvent(id)
  const photos = useEventPhotos(id)

  if (permsLoading || eventLoading) {
    return <div className="p-6 text-sm text-muted-foreground">Loading…</div>
  }
  // A hidden (audience-restricted) event 404s from the API — mirror that here.
  if (isError || !event || !has("photo:read")) {
    return <div className="p-6 text-sm text-muted-foreground">Event not found.</div>
  }

  return (
    <>
      <PageHeader title={`${event.name} — Photos`}>
        <Link
          href="/events"
          className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
        >
          <ArrowLeft className="mr-1.5 h-3.5 w-3.5" />
          Events
        </Link>
      </PageHeader>

      <div className="space-y-6 p-6">
        {has("photo:upload") && <PhotoUploader eventId={id} />}

        <PhotoGallery
          eventId={id}
          photos={photos.data ?? []}
          isLoading={photos.isLoading}
          canModerate={has("photo:moderate")}
          currentMemberId={session?.member?.id ?? null}
        />
      </div>
    </>
  )
}
