"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { apiErrorMessage } from "@/lib/api"
import { useCreateEventType } from "@/hooks/use-events"
import { EventTypeForm, type EventTypeFormValues } from "../event-type-form"

export default function NewEventTypePage() {
  const router = useRouter()
  const [error, setError] = useState<string | null>(null)
  const createEventType = useCreateEventType()

  function handleSubmit(values: EventTypeFormValues) {
    setError(null)
    createEventType.mutate(values, {
      onSuccess: () => router.push("/events/types"),
      onError: (err) =>
        setError(apiErrorMessage(err, { 409: "An event type with this name already exists." })),
    })
  }

  return (
    <EventTypeForm
      title="New Event Type"
      submitLabel="Create event type"
      submitting={createEventType.isPending}
      error={error}
      onSubmit={handleSubmit}
      onCancel={() => router.push("/events/types")}
    />
  )
}
