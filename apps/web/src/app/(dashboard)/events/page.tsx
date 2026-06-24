"use client"

import { CalendarPlus } from "lucide-react"
import { useMemo, useState } from "react"
import { PageHeader } from "@/components/page-header"
import { Button } from "@/components/ui/button"
import { useEvents, useEventTypes } from "@/hooks/use-events"
import type { Event } from "@/types/api"
import { buildColumns } from "./columns"
import { EventDetailSheet } from "./event-detail-sheet"
import { EventFilters, type TimeFilter } from "./event-filters"
import { EventsTable } from "./events-table"

export default function EventsPage() {
  const { data: events = [], isLoading: eventsLoading } = useEvents()
  const { data: eventTypes = [], isLoading: typesLoading } = useEventTypes()

  const [search, setSearch] = useState("")
  const [timeFilter, setTimeFilter] = useState<TimeFilter>("upcoming")
  const [typeIds, setTypeIds] = useState<string[]>([])
  const [selected, setSelected] = useState<Event | null>(null)
  const [sheetOpen, setSheetOpen] = useState(false)
  // Snapshot "now" once at mount so the render stays pure (re-filters on refresh).
  const [now] = useState(() => Date.now())

  const filtered = useMemo(() => {
    return events.filter((e) => {
      if (e.is_deleted) return false

      if (timeFilter !== "all") {
        const ends = new Date(e.scheduled_end).getTime()
        const isPast = !Number.isNaN(ends) && ends < now
        if (timeFilter === "upcoming" && isPast) return false
        if (timeFilter === "past" && !isPast) return false
      }

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
  }, [events, timeFilter, typeIds, search, now])

  const columns = useMemo(() => buildColumns(), [])

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
      <PageHeader title={`Events (${filtered.length})`}>
        <Button size="sm">
          <CalendarPlus className="mr-2 h-4 w-4" />
          Add Event
        </Button>
      </PageHeader>

      <div className="flex-1 space-y-4 p-4 md:p-6">
        <EventFilters
          search={search}
          timeFilter={timeFilter}
          typeIds={typeIds}
          eventTypes={eventTypes.filter((t) => t.is_active)}
          onSearchChange={setSearch}
          onTimeChange={setTimeFilter}
          onTypeToggle={toggleType}
          onClear={handleClear}
        />

        <EventsTable
          data={filtered}
          columns={columns}
          isLoading={eventsLoading || typesLoading}
          onRowClick={handleRowClick}
        />
      </div>

      <EventDetailSheet event={selected} open={sheetOpen} onOpenChange={setSheetOpen} />
    </>
  )
}
