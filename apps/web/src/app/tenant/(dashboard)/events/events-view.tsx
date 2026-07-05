"use client"

import { CalendarDays, CalendarPlus, List } from "lucide-react"
import { useMemo, useState } from "react"
import { useRouter } from "next/navigation"
import { PageHeader } from "@/components/page-header"
import { Button } from "@/components/ui/button"
import { usePermissions } from "@/hooks/use-session"
import { useEvents, useEventTypes } from "@/hooks/use-events"
import { addMonths, startOfMonth } from "@/lib/calendar"
import { cn } from "@/lib/utils"
import type { Event } from "@/types/api"
import { buildColumns } from "./columns"
import { EventCalendar } from "./event-calendar"
import { EventDetailSheet } from "./event-detail-sheet"
import { EventFilters, type TimeFilter } from "./event-filters"
import { EventsTable } from "./events-table"
import { CalendarSubscriptionDialog } from "./calendar-subscription-dialog"

export type View = "list" | "calendar"

/**
 * Shared Events surface, mounted at two routes: `/events` (List) and
 * `/events/calendar` (Calendar). The active view is the route, not local state —
 * the List/Calendar switch navigates so the sidebar highlight and the URL stay
 * in sync (see docs/spec/navigation.md). Filters are per-view by design.
 */
export function EventsView({ initialView }: { initialView: View }) {
  const router = useRouter()
  const view = initialView
  const { has } = usePermissions()
  const { data: events = [], isLoading: eventsLoading } = useEvents()
  const { data: eventTypes = [], isLoading: typesLoading } = useEventTypes()

  const [search, setSearch] = useState("")
  const [timeFilter, setTimeFilter] = useState<TimeFilter>("upcoming")
  const [typeIds, setTypeIds] = useState<string[]>([])
  const [selected, setSelected] = useState<Event | null>(null)
  const [sheetOpen, setSheetOpen] = useState(false)
  // Snapshot "today" once so renders stay pure.
  const [today] = useState(() => new Date())
  const [month, setMonth] = useState(() => startOfMonth(new Date()))

  // Search + type filter (shared by both views).
  const matched = useMemo(() => {
    return events.filter((e) => {
      if (e.is_deleted) return false
      if (typeIds.length > 0 && !typeIds.includes(e.event_type_id)) return false
      if (search) {
        const q = search.toLowerCase()
        const haystack = [e.name, e.location?.name, e.location_notes, e.event_type.name]
          .filter(Boolean)
          .join(" ")
          .toLowerCase()
        if (!haystack.includes(q)) return false
      }
      return true
    })
  }, [events, typeIds, search])

  // List view additionally narrows by the time window.
  const listEvents = useMemo(() => {
    if (timeFilter === "all") return matched
    const now = today.getTime()
    return matched.filter((e) => {
      const ends = new Date(e.scheduled_end).getTime()
      const isPast = !Number.isNaN(ends) && ends < now
      return timeFilter === "upcoming" ? !isPast : isPast
    })
  }, [matched, timeFilter, today])

  const columns = useMemo(() => buildColumns(), [])
  const count = view === "list" ? listEvents.length : matched.length

  function toggleType(id: string) {
    setTypeIds((prev) => (prev.includes(id) ? prev.filter((t) => t !== id) : [...prev, id]))
  }

  function handleClear() {
    setSearch("")
    setTimeFilter("upcoming")
    setTypeIds([])
  }

  function handleRowClick(event: Event) {
    setSelected(event)
    setSheetOpen(true)
  }

  return (
    <>
      <PageHeader title={`Events (${count})`}>
        <div className="flex items-center rounded-md border p-0.5">
          <ViewButton
            active={view === "list"}
            onClick={() => router.push("/events")}
            icon={List}
          >
            List
          </ViewButton>
          <ViewButton
            active={view === "calendar"}
            onClick={() => router.push("/events/calendar")}
            icon={CalendarDays}
          >
            Calendar
          </ViewButton>
        </div>
        <CalendarSubscriptionDialog />
        {has("event:create") && (
          <Button size="sm" onClick={() => router.push("/events/new")}>
            <CalendarPlus className="mr-2 h-4 w-4" />
            Add Event
          </Button>
        )}
      </PageHeader>

      <div className="flex-1 space-y-4 p-4 md:p-6">
        <EventFilters
          search={search}
          timeFilter={timeFilter}
          typeIds={typeIds}
          eventTypes={eventTypes.filter((t) => t.is_active)}
          showTimeFilter={view === "list"}
          onSearchChange={setSearch}
          onTimeChange={setTimeFilter}
          onTypeToggle={toggleType}
          onClear={handleClear}
        />

        {view === "list" ? (
          <EventsTable
            data={listEvents}
            columns={columns}
            isLoading={eventsLoading || typesLoading}
            onRowClick={handleRowClick}
          />
        ) : (
          <EventCalendar
            events={matched}
            month={month}
            today={today}
            onPrev={() => setMonth((m) => addMonths(m, -1))}
            onNext={() => setMonth((m) => addMonths(m, 1))}
            onToday={() => setMonth(startOfMonth(today))}
            onEventClick={handleRowClick}
          />
        )}
      </div>

      <EventDetailSheet event={selected} open={sheetOpen} onOpenChange={setSheetOpen} />
    </>
  )
}

function ViewButton({
  active,
  onClick,
  icon: Icon,
  children,
}: {
  active: boolean
  onClick: () => void
  icon: typeof List
  children: React.ReactNode
}) {
  return (
    <Button
      variant={active ? "secondary" : "ghost"}
      size="sm"
      onClick={onClick}
      className={cn("h-7 gap-1.5", !active && "text-muted-foreground")}
    >
      <Icon className="h-4 w-4" />
      {children}
    </Button>
  )
}
