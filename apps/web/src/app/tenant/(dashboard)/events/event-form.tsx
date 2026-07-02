"use client"

import { FormField, SectionTitle } from "@/components/form-helpers"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Separator } from "@/components/ui/separator"
import type { Event, EventType, Location } from "@/types/api"

export const NO_LOCATION = "__none__"

/** Format a Date as a `datetime-local` value ("YYYY-MM-DDTHH:mm") in local time. */
export function toLocalInput(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0")
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` +
    `T${pad(d.getHours())}:${pad(d.getMinutes())}`
  )
}

/** Next top-of-hour, local time, as a `datetime-local` string. */
export function defaultStart(): string {
  const d = new Date()
  d.setMinutes(0, 0, 0)
  d.setHours(d.getHours() + 1)
  return toLocalInput(d)
}

/** One hour after a `datetime-local` string. */
export function plusOneHour(start: string): string {
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
export function toUtcInstant(value: string, allDay: boolean): string {
  if (allDay) return `${value.slice(0, 10)}T00:00:00Z`
  return new Date(value).toISOString()
}

export type FormState = {
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
  // Activity metrics (edit page only; empty on create).
  camping_nights: string
  community_service_hours: string
  conservation_hours: string
  hiking_miles: string
  backpacking_miles: string
  paddling_miles: string
  cycling_miles: string
  water_hours: string
}

export function makeEmptyForm(): FormState {
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
    camping_nights: "",
    community_service_hours: "",
    conservation_hours: "",
    hiking_miles: "",
    backpacking_miles: "",
    paddling_miles: "",
    cycling_miles: "",
    water_hours: "",
  }
}

/** Seed a form from an existing event (for the edit page). */
export function toFormState(event: Event): FormState {
  const str = (v: string | number | null) => (v == null ? "" : String(v))
  // Convert a stored UTC instant back to the `datetime-local`/`date` input shape.
  const toInput = (iso: string, allDay: boolean) =>
    allDay ? `${iso.slice(0, 10)}T00:00` : toLocalInput(new Date(iso))
  return {
    name: event.name,
    event_type_id: event.event_type_id,
    location_id: event.location_id ?? "",
    location_notes: event.location_notes ?? "",
    departure_location: event.departure_location ?? "",
    return_location: event.return_location ?? "",
    video_conference_url: event.video_conference_url ?? "",
    scheduled_start: toInput(event.scheduled_start, event.all_day),
    scheduled_end: toInput(event.scheduled_end, event.all_day),
    all_day: event.all_day,
    signup_start: event.signup_start ?? "",
    signup_deadline: event.signup_deadline ?? "",
    signup_limit_scouts: str(event.signup_limit_scouts),
    signup_limit_adults: str(event.signup_limit_adults),
    cost_youth: str(event.cost_youth),
    cost_adult: str(event.cost_adult),
    description: event.description ?? "",
    agenda: event.agenda ?? "",
    camping_nights: str(event.camping_nights),
    community_service_hours: str(event.community_service_hours),
    conservation_hours: str(event.conservation_hours),
    hiking_miles: str(event.hiking_miles),
    backpacking_miles: str(event.backpacking_miles),
    paddling_miles: str(event.paddling_miles),
    cycling_miles: str(event.cycling_miles),
    water_hours: str(event.water_hours),
  }
}

export function toApiPayload(form: FormState, eventTypeId: string): Partial<Event> {
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
    camping_nights: intOrNull(form.camping_nights),
    community_service_hours: nullify(form.community_service_hours),
    conservation_hours: nullify(form.conservation_hours),
    hiking_miles: nullify(form.hiking_miles),
    backpacking_miles: nullify(form.backpacking_miles),
    paddling_miles: nullify(form.paddling_miles),
    cycling_miles: nullify(form.cycling_miles),
    water_hours: nullify(form.water_hours),
  }
}

interface EventFormFieldsProps {
  form: FormState
  set: <K extends keyof FormState>(key: K, value: FormState[K]) => void
  /** Active event types for the type Select. */
  eventTypes: EventType[]
  locations: Location[]
  /** The resolved type id (explicit choice, else first active type). */
  effectiveTypeId: string
  /** Show the Activity metrics section (edit page only). */
  showActivity?: boolean
}

/**
 * The scalar event fields shared by the create and edit pages: Basics, When, Where,
 * Sign-up & cost, Details, and (edit only) Activity. Audiences and organizers are
 * separate sub-resources handled outside this component.
 */
export function EventFormFields({
  form,
  set,
  eventTypes,
  locations,
  effectiveTypeId,
  showActivity = false,
}: EventFormFieldsProps) {
  const handleText = (key: keyof FormState) => (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>,
  ) => set(key, e.target.value as FormState[typeof key])

  // When toggling all-day, normalize the start/end times so the date inputs stay valid.
  function toggleAllDay(checked: boolean) {
    set("all_day", checked)
    if (checked) {
      set("scheduled_start", `${form.scheduled_start.slice(0, 10)}T00:00`)
      set("scheduled_end", `${form.scheduled_end.slice(0, 10)}T00:00`)
    }
  }

  return (
    <>
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
          {eventTypes.length === 0 ? (
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
                  {eventTypes.find((t) => t.id === effectiveTypeId)?.name}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                {eventTypes.map((t) => (
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

      {showActivity && (
        <>
          <Separator />

          {/* ── Activity ───────────────────────────────────── */}
          <SectionTitle>Activity</SectionTitle>
          <div className="grid grid-cols-2 gap-4">
            <FormField label="Camping nights">
              <Input type="number" min={0} value={form.camping_nights} onChange={handleText("camping_nights")} />
            </FormField>
            <FormField label="Service hours">
              <Input type="number" min={0} step="0.01" value={form.community_service_hours} onChange={handleText("community_service_hours")} />
            </FormField>
            <FormField label="Conservation hours">
              <Input type="number" min={0} step="0.01" value={form.conservation_hours} onChange={handleText("conservation_hours")} />
            </FormField>
            <FormField label="Water hours">
              <Input type="number" min={0} step="0.01" value={form.water_hours} onChange={handleText("water_hours")} />
            </FormField>
            <FormField label="Hiking miles">
              <Input type="number" min={0} step="0.01" value={form.hiking_miles} onChange={handleText("hiking_miles")} />
            </FormField>
            <FormField label="Backpacking miles">
              <Input type="number" min={0} step="0.01" value={form.backpacking_miles} onChange={handleText("backpacking_miles")} />
            </FormField>
            <FormField label="Paddling miles">
              <Input type="number" min={0} step="0.01" value={form.paddling_miles} onChange={handleText("paddling_miles")} />
            </FormField>
            <FormField label="Cycling miles">
              <Input type="number" min={0} step="0.01" value={form.cycling_miles} onChange={handleText("cycling_miles")} />
            </FormField>
          </div>
        </>
      )}
    </>
  )
}
