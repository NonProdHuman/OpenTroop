"use client"

import { useState } from "react"
import Link from "next/link"
import { CalendarDays } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { formatEventWhen } from "@/lib/format"
import { useEvents } from "@/hooks/use-events"
import { EventRsvpPanel } from "../events/event-rsvp-panel"
import type { Event } from "@/types/api"

const MAX_EVENTS = 5

/** Next few visible events, each with the shared per-household RSVP panel
 * (reuses `EventRsvpPanel` → `MemberRsvpRow` → the participant mutation and the
 * quick RSVP control from the event page, including permission-slip indicators). */
export function FamilyEvents() {
  const { data: events, isLoading } = useEvents()
  const [now] = useState(() => Date.now())

  if (isLoading) return <Skeleton className="h-40 w-full" />

  const upcoming = (events ?? [])
    .filter((e) => new Date(e.scheduled_end ?? e.scheduled_start).getTime() >= now)
    .sort(
      (a, b) => new Date(a.scheduled_start).getTime() - new Date(b.scheduled_start).getTime(),
    )
    .slice(0, MAX_EVENTS)

  if (upcoming.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">No upcoming events on your calendar.</p>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      {upcoming.map((event: Event) => (
        <Card key={event.id} data-testid="family-event">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-base">
              <CalendarDays className="h-4 w-4 shrink-0 text-muted-foreground" />
              <Link href={`/events?event=${event.id}`} className="hover:underline">
                {event.name}
              </Link>
            </CardTitle>
            <p className="text-xs text-muted-foreground">
              {formatEventWhen(event.scheduled_start, event.scheduled_end, event.all_day)}
            </p>
          </CardHeader>
          <CardContent>
            {event.event_type.allow_signups ? (
              <EventRsvpPanel event={event} />
            ) : (
              <p className="text-xs text-muted-foreground">No RSVP needed for this event.</p>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
