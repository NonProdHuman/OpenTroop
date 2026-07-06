"use client"

import { useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { apiErrorMessage } from "@/lib/api"
import { PageHeader } from "@/components/page-header"
import { useEventType, useUpdateEventType, useDeleteEventType } from "@/hooks/use-events"
import { usePermissions } from "@/hooks/use-session"
import { EventTypeForm, type EventTypeFormValues } from "../../event-type-form"

export default function EditEventTypePage() {
  const router = useRouter()
  const { id } = useParams<{ id: string }>()
  const { has } = usePermissions()
  const { data: eventType, isLoading } = useEventType(id)
  const updateEventType = useUpdateEventType()
  const deleteEventType = useDeleteEventType()
  const [error, setError] = useState<string | null>(null)

  if (isLoading) {
    return (
      <>
        <PageHeader title="Edit Event Type" />
        <div className="p-4 md:p-6">
          <p className="text-sm text-muted-foreground">Loading…</p>
        </div>
      </>
    )
  }

  if (!eventType) {
    return (
      <>
        <PageHeader title="Edit Event Type" />
        <div className="p-4 md:p-6">
          <p className="text-sm text-destructive">Event type not found.</p>
        </div>
      </>
    )
  }

  function handleSubmit(values: EventTypeFormValues) {
    setError(null)
    updateEventType.mutate(
      { id, data: values },
      {
        onSuccess: () => router.push("/events/types"),
        onError: (err) =>
          setError(apiErrorMessage(err, { 409: "An event type with this name already exists." })),
      },
    )
  }

  function handleDelete() {
    setError(null)
    deleteEventType.mutate(id, {
      onSuccess: () => router.push("/events/types"),
      onError: (err) => setError(apiErrorMessage(err)),
    })
  }

  return (
    <EventTypeForm
      title={`Edit ${eventType.name}`}
      initial={eventType}
      submitLabel="Save changes"
      submitting={updateEventType.isPending}
      error={error}
      onSubmit={handleSubmit}
      onCancel={() => router.push("/events/types")}
      onDelete={handleDelete}
      deleting={deleteEventType.isPending}
      deletable={has("event:delete") && !eventType.is_system}
    />
  )
}
