import { describe, expect, it } from "vitest"
import type { Event } from "@/types/api"
import { addMonths, buildMonthGrid, dayKey, eventsByDay, startOfMonth } from "./calendar"

describe("buildMonthGrid", () => {
  it("returns 6 weeks of 7 days, Sunday-first", () => {
    const grid = buildMonthGrid(new Date(2026, 6, 15)) // July 2026
    expect(grid).toHaveLength(6)
    expect(grid.every((w) => w.length === 7)).toBe(true)
    expect(grid[0][0].date.getDay()).toBe(0) // Sunday
  })

  it("marks in-month vs leading/trailing days", () => {
    // July 1 2026 is a Wednesday, so the grid starts on Sun Jun 28.
    const grid = buildMonthGrid(new Date(2026, 6, 1))
    expect(grid[0][0].inMonth).toBe(false) // Jun 28
    expect(grid[0][3].inMonth).toBe(true) // Jul 1
    expect(grid[0][3].date.getDate()).toBe(1)
  })

  it("flags today", () => {
    const today = new Date(2026, 6, 10)
    const grid = buildMonthGrid(new Date(2026, 6, 1), today)
    const flagged = grid.flat().filter((c) => c.isToday)
    expect(flagged).toHaveLength(1)
    expect(flagged[0].key).toBe(dayKey(today))
  })
})

describe("startOfMonth / addMonths", () => {
  it("normalizes to the first of the month", () => {
    expect(startOfMonth(new Date(2026, 6, 22)).getDate()).toBe(1)
  })

  it("wraps year boundaries", () => {
    const dec = new Date(2026, 11, 1)
    expect(addMonths(dec, 1).getFullYear()).toBe(2027)
    expect(addMonths(dec, 1).getMonth()).toBe(0)
  })
})

function evt(over: Partial<Event>): Event {
  return {
    id: "e",
    tenant_id: "t",
    created_at: "",
    updated_at: "",
    is_deleted: false,
    name: "E",
    event_type_id: "et",
    location_id: null,
    location_notes: null,
    departure_location: null,
    return_location: null,
    scheduled_start: "2026-07-10T15:00:00Z",
    scheduled_end: "2026-07-10T17:00:00Z",
    all_day: false,
    signup_start: null,
    signup_deadline: null,
    signup_limit_scouts: null,
    signup_limit_adults: null,
    cost_youth: null,
    cost_adult: null,
    video_conference_url: null,
    description: null,
    agenda: null,
    tour_permit_submitted: null,
    cancelled_at: null,
    attendance_taken: false,
    linked_event_id: null,
    community_service_hours: null,
    conservation_hours: null,
    hiking_miles: null,
    backpacking_miles: null,
    paddling_miles: null,
    cycling_miles: null,
    water_hours: null,
    camping_nights: null,
    event_type: {
      id: "et",
      tenant_id: "t",
      created_at: "",
      updated_at: "",
      is_deleted: false,
      name: "Campout",
      color: "#2ECC71",
      is_active: true,
      is_system: true,
      tracks_service_hours: false,
      tracks_camping_nights: true,
      tracks_mileage: true,
      allow_signups: true,
      require_permission_slip: true,
      allow_guests: false,
      is_online: false,
    },
    location: null,
    ...over,
  }
}

describe("eventsByDay", () => {
  it("buckets a single-day event under one local day", () => {
    const map = eventsByDay([evt({ id: "a", scheduled_start: "2026-07-10T15:00:00Z" })])
    const key = dayKey(new Date("2026-07-10T15:00:00Z"))
    expect(map.get(key)?.map((e) => e.id)).toEqual(["a"])
  })

  it("places a multi-day event on every spanned day", () => {
    const start = "2026-07-10T15:00:00Z"
    const end = "2026-07-12T15:00:00Z"
    const map = eventsByDay([evt({ id: "camp", scheduled_start: start, scheduled_end: end })])
    const days = [
      dayKey(new Date(start)),
      dayKey(new Date("2026-07-11T15:00:00Z")),
      dayKey(new Date(end)),
    ]
    for (const d of days) expect(map.get(d)?.some((e) => e.id === "camp")).toBe(true)
  })

  it("buckets an all-day event by its UTC date, not the local date", () => {
    const map = eventsByDay([
      evt({
        id: "ad",
        all_day: true,
        scheduled_start: "2026-07-10T00:00:00Z",
        scheduled_end: "2026-07-10T00:00:00Z",
      }),
    ])
    // Key is built from the UTC calendar date (Jul 10) so it never slips a day.
    const key = dayKey(new Date(2026, 6, 10))
    expect(map.get(key)?.map((e) => e.id)).toEqual(["ad"])
  })
})
