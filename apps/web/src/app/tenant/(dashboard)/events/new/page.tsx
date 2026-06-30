"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { useCreateEvent, useEventTypes, useLocations } from "@/hooks/use-events"
import { PageHeader } from "@/components/page-header"
import { Button } from "@/components/ui/button"
import {
  EventFormFields,
  makeEmptyForm,
  toApiPayload,
  type FormState,
} from "../event-form"

export default function NewEventPage() {
  const router = useRouter()
  const createEvent = useCreateEvent()
  const { data: eventTypes = [] } = useEventTypes()
  const { data: locations = [] } = useLocations()

  const activeTypes = eventTypes.filter((t) => t.is_active)

  const [form, setForm] = useState<FormState>(() => makeEmptyForm())
  const [error, setError] = useState<string | null>(null)

  // The effective event type: the explicit choice, else the first active type.
  const effectiveTypeId = form.event_type_id || activeTypes[0]?.id || ""

  function set<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  async function handleSave() {
    if (!form.name.trim()) {
      setError("Event name is required.")
      return
    }
    if (!effectiveTypeId) {
      setError("Select an event type. (Manage types in Settings.)")
      return
    }
    if (!form.scheduled_start || !form.scheduled_end) {
      setError("Start and end times are required.")
      return
    }
    if (new Date(form.scheduled_end) < new Date(form.scheduled_start)) {
      setError("End time cannot be before the start time.")
      return
    }
    setError(null)
    createEvent.mutate(toApiPayload(form, effectiveTypeId), {
      onSuccess: () => router.push("/events"),
      onError: (err) => {
        const msg = err instanceof Error ? err.message : String(err)
        if (msg.toLowerCase().includes("403")) {
          setError("You don't have permission to add events.")
        } else if (
          msg.toLowerCase().includes("load failed") ||
          msg.toLowerCase().includes("failed to fetch")
        ) {
          setError("Could not reach the backend — is the server running?")
        } else {
          setError("Something went wrong — please try again.")
        }
      },
    })
  }

  return (
    <>
      <PageHeader title="New event">
        <Button variant="outline" onClick={() => router.push("/events")}>
          Cancel
        </Button>
        <Button onClick={handleSave} disabled={createEvent.isPending}>
          {createEvent.isPending ? "Creating…" : "Create event"}
        </Button>
      </PageHeader>

      <div className="max-w-2xl mx-auto p-4 md:p-6 space-y-6">
        {error && <p className="text-sm text-destructive">{error}</p>}

        <EventFormFields
          form={form}
          set={set}
          eventTypes={activeTypes}
          locations={locations}
          effectiveTypeId={effectiveTypeId}
        />

        <div className="flex justify-end gap-3 pt-2">
          <Button variant="outline" onClick={() => router.push("/events")}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={createEvent.isPending}>
            {createEvent.isPending ? "Creating…" : "Create event"}
          </Button>
        </div>
      </div>
    </>
  )
}
