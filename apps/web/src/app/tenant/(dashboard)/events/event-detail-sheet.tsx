"use client"

import { useRouter } from "next/navigation"
import { Pencil } from "lucide-react"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { Field, Section } from "@/components/detail-helpers"
import { formatDate, formatDateTime, formatMoney } from "@/lib/format"
import { usePermissions } from "@/hooks/use-session"
import type { Event } from "@/types/api"
import { EventRsvpPanel } from "./event-rsvp-panel"
import { EventTypeBadge } from "./event-type-badge"

interface EventDetailSheetProps {
  event: Event | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function EventDetailSheet({ event, open, onOpenChange }: EventDetailSheetProps) {
  const router = useRouter()
  const { has } = usePermissions()

  if (!event) return null

  function handleEdit() {
    onOpenChange(false)
    router.push(`/events/${event!.id}/edit`)
  }

  const loc = event.location
  const address = loc
    ? [
        loc.street1,
        loc.street2,
        loc.city && loc.state
          ? `${loc.city}, ${loc.state} ${loc.postal_code ?? ""}`.trim()
          : (loc.city ?? loc.state),
      ]
        .filter(Boolean)
        .join(", ")
    : null

  const signupWindow =
    event.signup_start || event.signup_deadline
      ? `${formatDate(event.signup_start) ?? "—"} → ${formatDate(event.signup_deadline) ?? "—"}`
      : null

  const mileage = [
    ["Hiking", event.hiking_miles],
    ["Backpacking", event.backpacking_miles],
    ["Paddling", event.paddling_miles],
    ["Cycling", event.cycling_miles],
  ].filter(([, v]) => v != null) as [string, string][]

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
        <SheetHeader>
          <SheetTitle>{event.name}</SheetTitle>
          <SheetDescription className="flex items-center gap-2">
            <EventTypeBadge type={event.event_type} />
          </SheetDescription>
          {has("event:write") && (
            <div className="flex items-center gap-2 pt-1">
              <Button size="sm" variant="outline" onClick={handleEdit}>
                <Pencil className="h-3.5 w-3.5 mr-1.5" />
                Edit
              </Button>
            </div>
          )}
        </SheetHeader>

        <div className="space-y-6 px-4 pb-8">
          <Section title="When">
            <Field
              label="Starts"
              value={formatDateTime(event.scheduled_start, {
                dateOnly: event.all_day,
                utc: event.all_day,
              })}
            />
            <Field
              label="Ends"
              value={formatDateTime(event.scheduled_end, {
                dateOnly: event.all_day,
                utc: event.all_day,
              })}
            />
            <Field label="All day" value={event.all_day ? "Yes" : null} />
          </Section>

          <Separator />

          <Section title="Where">
            <Field label="Location" value={loc?.name} />
            <Field label="Address" value={address} />
            <Field label="Notes" value={event.location_notes} />
            <Field label="Departure" value={event.departure_location} />
            <Field label="Return" value={event.return_location} />
            <Field
              label="Video call"
              value={
                event.video_conference_url ? (
                  <a
                    href={event.video_conference_url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-primary underline-offset-4 hover:underline"
                  >
                    Join link
                  </a>
                ) : null
              }
            />
          </Section>

          <Separator />

          <Section title="Sign-up & cost">
            <Field label="Sign-up window" value={signupWindow} />
            <Field label="Scout limit" value={event.signup_limit_scouts} />
            <Field label="Adult limit" value={event.signup_limit_adults} />
            <Field label="Youth cost" value={formatMoney(event.cost_youth)} />
            <Field label="Adult cost" value={formatMoney(event.cost_adult)} />
          </Section>

          {event.description || event.agenda ? (
            <>
              <Separator />
              <Section title="Details">
                <Field label="Description" value={event.description} />
                <Field label="Agenda" value={event.agenda} />
              </Section>
            </>
          ) : null}

          {event.camping_nights != null ||
          event.community_service_hours != null ||
          event.conservation_hours != null ||
          mileage.length > 0 ? (
            <>
              <Separator />
              <Section title="Activity">
                <Field label="Camping nights" value={event.camping_nights} />
                <Field label="Service hours" value={event.community_service_hours} />
                <Field label="Conservation hours" value={event.conservation_hours} />
                {mileage.map(([label, v]) => (
                  <Field key={label} label={`${label} miles`} value={v} />
                ))}
              </Section>
            </>
          ) : null}

          {event.event_type.allow_signups && (
            <>
              <Separator />
              <EventRsvpPanel event={event} />
            </>
          )}

          <Separator />

          <Section title="Status">
            <Field label="Attendance taken" value={event.attendance_taken ? "Yes" : "Not yet"} />
            <Field
              label="Permission slip"
              value={event.event_type.require_permission_slip ? "Required" : null}
            />
            <Field
              label="Tour permit"
              value={
                event.tour_permit_submitted === null
                  ? null
                  : event.tour_permit_submitted
                    ? "Submitted"
                    : "Not submitted"
              }
            />
          </Section>
        </div>
      </SheetContent>
    </Sheet>
  )
}
