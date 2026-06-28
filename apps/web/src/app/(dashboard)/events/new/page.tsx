"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { useCreateEvent, useEventTypes, useLocations } from "@/hooks/use-events"
import { PageHeader } from "@/components/page-header"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Separator } from "@/components/ui/separator"
import type { Event } from "@/types/api"

const NO_LOCATION = "__none__"

/** Format a Date as a `datetime-local` value ("YYYY-MM-DDTHH:mm") in local time. */
function toLocalInput(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0")
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` +
    `T${pad(d.getHours())}:${pad(d.getMinutes())}`
  )
}

/** Next top-of-hour, local time, as a `datetime-local` string. */
function defaultStart(): string {
  const d = new Date()
  d.setMinutes(0, 0, 0)
  d.setHours(d.getHours() + 1)
  return toLocalInput(d)
}

/** One hour after a `datetime-local` string. */
function plusOneHour(start: string): string {
  const d = new Date(start)
  if (Number.isNaN(d.getTime())) return start
  d.setHours(d.getHours() + 1)
  return toLocalInput(d)
}

/**
 * Convert a form value to a UTC ISO instant for the API. Timed values are local
 * wall-clock times → convert through `Date` to UTC. All-day values are a bare
 * calendar date → pin to UTC midnight so the date is preserved across timezones.
 */
function toUtcInstant(value: string, allDay: boolean): string {
  if (allDay) return `${value.slice(0, 10)}T00:00:00Z`
  return new Date(value).toISOString()
}

type FormState = {
  name: string
  event_type_id: string
  location_id: string
  location_notes: string
  departure_location: string
  return_location: string
  video_conference_url: string
  scheduled_start: string
  scheduled_end: string
  all_day: boolean
  signup_start: string
  signup_deadline: string
  signup_limit_scouts: string
  signup_limit_adults: string
  cost_youth: string
  cost_adult: string
  description: string
  agenda: string
}

function makeEmptyForm(): FormState {
  const start = defaultStart()
  return {
    name: "",
    event_type_id: "",
    location_id: "",
    location_notes: "",
    departure_location: "",
    return_location: "",
    video_conference_url: "",
    scheduled_start: start,
    scheduled_end: plusOneHour(start),
    all_day: false,
    signup_start: "",
    signup_deadline: "",
    signup_limit_scouts: "",
    signup_limit_adults: "",
    cost_youth: "",
    cost_adult: "",
    description: "",
    agenda: "",
  }
}

function toApiPayload(form: FormState, eventTypeId: string): Partial<Event> {
  const nullify = (v: string) => v.trim() || null
  const intOrNull = (v: string) => {
    const n = parseInt(v, 10)
    return Number.isNaN(n) ? null : n
  }
  return {
    name: form.name.trim(),
    event_type_id: eventTypeId,
    location_id: form.location_id || null,
    location_notes: nullify(form.location_notes),
    departure_location: nullify(form.departure_location),
    return_location: nullify(form.return_location),
    video_conference_url: nullify(form.video_conference_url),
    scheduled_start: toUtcInstant(form.scheduled_start, form.all_day),
    scheduled_end: toUtcInstant(form.scheduled_end, form.all_day),
    all_day: form.all_day,
    signup_start: nullify(form.signup_start),
    signup_deadline: nullify(form.signup_deadline),
    signup_limit_scouts: intOrNull(form.signup_limit_scouts),
    signup_limit_adults: intOrNull(form.signup_limit_adults),
    cost_youth: nullify(form.cost_youth),
    cost_adult: nullify(form.cost_adult),
    description: nullify(form.description),
    agenda: nullify(form.agenda),
  }
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground pt-2">
      {children}
    </h2>
  )
}

function FormField({
  label,
  children,
  required,
}: {
  label: string
  children: React.ReactNode
  required?: boolean
}) {
  return (
    <div className="space-y-1.5">
      <Label>
        {label}
        {required && <span className="text-destructive ml-0.5">*</span>}
      </Label>
      {children}
    </div>
  )
}

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

  function handleText(key: keyof FormState) {
    return (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      set(key, e.target.value as FormState[typeof key])
  }

  // When toggling all-day, normalize the start/end times so the date inputs stay valid.
  function toggleAllDay(checked: boolean) {
    setForm((prev) => ({
      ...prev,
      all_day: checked,
      scheduled_start: checked
        ? `${prev.scheduled_start.slice(0, 10)}T00:00`
        : prev.scheduled_start,
      scheduled_end: checked
        ? `${prev.scheduled_end.slice(0, 10)}T00:00`
        : prev.scheduled_end,
    }))
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

        {/* ── Basics ───────────────────────────────────────── */}
        <SectionTitle>Basics</SectionTitle>
        <div className="grid grid-cols-2 gap-4">
          <div className="col-span-2">
            <FormField label="Name" required>
              <Input
                value={form.name}
                onChange={handleText("name")}
                placeholder="e.g. Fall Campout, Troop Meeting"
                autoFocus
              />
            </FormField>
          </div>
          <FormField label="Event type" required>
            {activeTypes.length === 0 ? (
              <p className="text-sm text-muted-foreground py-2">
                No active event types — add one in Settings.
              </p>
            ) : (
              <Select
                value={effectiveTypeId}
                onValueChange={(v) => set("event_type_id", v as string)}
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select event type...">
                    {activeTypes.find(t => t.id === effectiveTypeId)?.name}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {activeTypes.map((t) => (
                    <SelectItem key={t.id} value={t.id}>
                      {t.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </FormField>
        </div>

        <Separator />

        {/* ── When ─────────────────────────────────────────── */}
        <div className="flex items-center gap-3">
          <SectionTitle>When</SectionTitle>
          <label className="flex items-center gap-2 text-sm cursor-pointer ml-auto">
            <input
              type="checkbox"
              checked={form.all_day}
              onChange={(e) => toggleAllDay(e.target.checked)}
              className="rounded"
            />
            All day
          </label>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <FormField label="Starts" required>
            {form.all_day ? (
              <Input
                type="date"
                value={form.scheduled_start.slice(0, 10)}
                onChange={(e) => set("scheduled_start", `${e.target.value}T00:00`)}
              />
            ) : (
              <Input
                type="datetime-local"
                value={form.scheduled_start}
                onChange={handleText("scheduled_start")}
              />
            )}
          </FormField>
          <FormField label="Ends" required>
            {form.all_day ? (
              <Input
                type="date"
                value={form.scheduled_end.slice(0, 10)}
                onChange={(e) => set("scheduled_end", `${e.target.value}T00:00`)}
              />
            ) : (
              <Input
                type="datetime-local"
                value={form.scheduled_end}
                onChange={handleText("scheduled_end")}
              />
            )}
          </FormField>
        </div>

        <Separator />

        {/* ── Where ────────────────────────────────────────── */}
        <SectionTitle>Where</SectionTitle>
        <div className="grid grid-cols-2 gap-4">
          <FormField label="Location">
            <Select
              value={form.location_id || NO_LOCATION}
              onValueChange={(v) => set("location_id", v === NO_LOCATION ? "" : (v as string))}
            >
              <SelectTrigger className="w-full"><SelectValue placeholder="— None —" /></SelectTrigger>
              <SelectContent>
                <SelectItem value={NO_LOCATION}>— None —</SelectItem>
                {locations.map((l) => (
                  <SelectItem key={l.id} value={l.id}>
                    {l.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </FormField>
          <FormField label="Location notes">
            <Input
              value={form.location_notes}
              onChange={handleText("location_notes")}
              placeholder="One-off spot, room, etc."
            />
          </FormField>
          <FormField label="Departure location">
            <Input value={form.departure_location} onChange={handleText("departure_location")} />
          </FormField>
          <FormField label="Return location">
            <Input value={form.return_location} onChange={handleText("return_location")} />
          </FormField>
          <div className="col-span-2">
            <FormField label="Video conference URL">
              <Input
                type="url"
                value={form.video_conference_url}
                onChange={handleText("video_conference_url")}
                placeholder="https://…"
              />
            </FormField>
          </div>
        </div>

        <Separator />

        {/* ── Sign-up & cost ───────────────────────────────── */}
        <SectionTitle>Sign-up &amp; cost</SectionTitle>
        <div className="grid grid-cols-2 gap-4">
          <FormField label="Sign-up opens">
            <Input type="date" value={form.signup_start} onChange={handleText("signup_start")} />
          </FormField>
          <FormField label="Sign-up deadline">
            <Input type="date" value={form.signup_deadline} onChange={handleText("signup_deadline")} />
          </FormField>
          <FormField label="Scout limit">
            <Input type="number" min={0} value={form.signup_limit_scouts} onChange={handleText("signup_limit_scouts")} />
          </FormField>
          <FormField label="Adult limit">
            <Input type="number" min={0} value={form.signup_limit_adults} onChange={handleText("signup_limit_adults")} />
          </FormField>
          <FormField label="Youth cost">
            <Input type="number" min={0} step="0.01" value={form.cost_youth} onChange={handleText("cost_youth")} placeholder="0.00" />
          </FormField>
          <FormField label="Adult cost">
            <Input type="number" min={0} step="0.01" value={form.cost_adult} onChange={handleText("cost_adult")} placeholder="0.00" />
          </FormField>
        </div>

        <Separator />

        {/* ── Details ──────────────────────────────────────── */}
        <SectionTitle>Details</SectionTitle>
        <FormField label="Description">
          <Textarea value={form.description} onChange={handleText("description")} rows={3} />
        </FormField>
        <FormField label="Agenda">
          <Textarea value={form.agenda} onChange={handleText("agenda")} rows={3} />
        </FormField>

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
