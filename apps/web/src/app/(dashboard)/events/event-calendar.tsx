"use client"

import { ChevronLeft, ChevronRight } from "lucide-react"
import { useMemo } from "react"
import { Button } from "@/components/ui/button"
import { buildMonthGrid, eventsByDay } from "@/lib/calendar"
import { cn } from "@/lib/utils"
import type { Event } from "@/types/api"

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
const MAX_CHIPS = 3

interface EventCalendarProps {
  events: Event[]
  month: Date
  today: Date
  onPrev: () => void
  onNext: () => void
  onToday: () => void
  onEventClick: (event: Event) => void
}

export function EventCalendar({
  events,
  month,
  today,
  onPrev,
  onNext,
  onToday,
  onEventClick,
}: EventCalendarProps) {
  const weeks = useMemo(() => buildMonthGrid(month, today), [month, today])
  const byDay = useMemo(() => eventsByDay(events), [events])
  const monthLabel = month.toLocaleDateString("en-US", { month: "long", year: "numeric" })

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold">{monthLabel}</h2>
        <div className="flex items-center gap-1">
          <Button variant="outline" size="sm" onClick={onToday} className="h-8">
            Today
          </Button>
          <Button variant="outline" size="icon" onClick={onPrev} className="h-8 w-8" aria-label="Previous month">
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <Button variant="outline" size="icon" onClick={onNext} className="h-8 w-8" aria-label="Next month">
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <div className="overflow-hidden rounded-md border">
        <div className="grid grid-cols-7 border-b bg-muted/40">
          {WEEKDAYS.map((d) => (
            <div key={d} className="px-2 py-1.5 text-center text-xs font-medium text-muted-foreground">
              {d}
            </div>
          ))}
        </div>

        <div className="grid grid-cols-7">
          {weeks.flat().map((cell) => {
            const dayEvents = byDay.get(cell.key) ?? []
            const shown = dayEvents.slice(0, MAX_CHIPS)
            const extra = dayEvents.length - shown.length
            return (
              <div
                key={cell.key}
                className={cn(
                  "min-h-24 border-b border-r p-1 last:border-r-0 [&:nth-child(7n)]:border-r-0",
                  !cell.inMonth && "bg-muted/20",
                )}
              >
                <div
                  className={cn(
                    "mb-1 flex h-5 w-5 items-center justify-center rounded-full text-xs",
                    cell.inMonth ? "text-foreground" : "text-muted-foreground/60",
                    cell.isToday && "bg-primary font-semibold text-primary-foreground",
                  )}
                >
                  {cell.date.getDate()}
                </div>
                <div className="space-y-0.5">
                  {shown.map((e) => (
                    <button
                      key={`${cell.key}-${e.id}`}
                      type="button"
                      onClick={() => onEventClick(e)}
                      title={e.name}
                      className="block w-full truncate rounded-sm bg-muted/60 px-1.5 py-0.5 text-left text-xs hover:bg-muted"
                      style={{ borderLeft: `3px solid ${e.event_type.color ?? "#6b7280"}` }}
                    >
                      {e.name}
                    </button>
                  ))}
                  {extra > 0 ? (
                    <span className="block px-1.5 text-xs text-muted-foreground">+{extra} more</span>
                  ) : null}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
