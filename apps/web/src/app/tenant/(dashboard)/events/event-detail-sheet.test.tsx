/* eslint-disable @typescript-eslint/no-explicit-any */
import React from "react"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { EventDetailSheet } from "./event-detail-sheet"
import * as sessionHook from "@/hooks/use-session"
import type { Event, EventType, Location } from "@/types/api"

const mockPush = vi.fn()

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}))

vi.mock("@/hooks/use-session", () => ({
  usePermissions: vi.fn(),
}))

// The RSVP panel has its own hooks and tests — stub it here.
vi.mock("./event-rsvp-panel", () => ({
  EventRsvpPanel: () => <div data-testid="rsvp-panel" />,
}))

const makeEventType = (overrides: Partial<EventType> = {}): EventType => ({
  id: "et1",
  tenant_id: "t1",
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
  is_deleted: false,
  name: "Campout",
  color: "#22C55E",
  is_active: true,
  is_system: true,
  tracks_service_hours: false,
  tracks_camping_nights: true,
  tracks_mileage: true,
  allow_signups: true,
  require_permission_slip: true,
  allow_guests: false,
  is_online: false,
  ...overrides,
})

const makeLocation = (overrides: Partial<Location> = {}): Location => ({
  id: "loc1",
  tenant_id: "t1",
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
  is_deleted: false,
  name: "Camp Wilderness",
  street1: "1 Trail Rd",
  street2: null,
  city: "Pinetop",
  state: "AZ",
  postal_code: "85935",
  country: null,
  phone: null,
  website_url: null,
  directions: null,
  description: null,
  distance_miles: null,
  ...overrides,
})

const makeEvent = (overrides: Partial<Event> = {}): Event => ({
  id: "e1",
  tenant_id: "t1",
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
  is_deleted: false,
  name: "Spring Campout",
  event_type_id: "et1",
  location_id: null,
  location_notes: null,
  departure_location: null,
  return_location: null,
  scheduled_start: "2024-05-03T17:00:00Z",
  scheduled_end: "2024-05-05T18:00:00Z",
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
  event_type: makeEventType(),
  location: null,
  ...overrides,
})

function setPermissions(granted: string[]) {
  vi.mocked(sessionHook.usePermissions).mockReturnValue({
    has: (p: string) => granted.includes(p),
    isMember: true,
    isLoading: false,
  } as any)
}

describe("EventDetailSheet", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setPermissions([])
  })

  it("renders nothing when event is null", () => {
    const { container } = render(
      <EventDetailSheet event={null} open={true} onOpenChange={vi.fn()} />,
    )
    expect(container).toBeEmptyDOMElement()
  })

  it("renders the event name, type badge, and schedule", () => {
    render(<EventDetailSheet event={makeEvent()} open={true} onOpenChange={vi.fn()} />)

    expect(screen.getByText("Spring Campout")).toBeInTheDocument()
    expect(screen.getByText("Campout")).toBeInTheDocument()
    expect(screen.getByText("Starts")).toBeInTheDocument()
    expect(screen.getByText("Ends")).toBeInTheDocument()
  })

  it("renders the location name and joined address", () => {
    render(
      <EventDetailSheet
        event={makeEvent({ location: makeLocation() })}
        open={true}
        onOpenChange={vi.fn()}
      />,
    )

    expect(screen.getByText("Camp Wilderness")).toBeInTheDocument()
    expect(screen.getByText("1 Trail Rd, Pinetop, AZ 85935")).toBeInTheDocument()
  })

  it("renders costs and the video-call link", () => {
    render(
      <EventDetailSheet
        event={makeEvent({
          cost_youth: "25.00",
          cost_adult: "10.5",
          video_conference_url: "https://meet.example.com/troop",
        })}
        open={true}
        onOpenChange={vi.fn()}
      />,
    )

    expect(screen.getByText("$25.00")).toBeInTheDocument()
    expect(screen.getByText("$10.50")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "Join link" })).toHaveAttribute(
      "href",
      "https://meet.example.com/troop",
    )
  })

  it("hides the Edit button without event:write", () => {
    render(<EventDetailSheet event={makeEvent()} open={true} onOpenChange={vi.fn()} />)
    expect(screen.queryByRole("button", { name: /edit/i })).not.toBeInTheDocument()
  })

  it("navigates to the edit page with event:write", async () => {
    setPermissions(["event:write"])
    const onOpenChange = vi.fn()

    render(<EventDetailSheet event={makeEvent()} open={true} onOpenChange={onOpenChange} />)

    await userEvent.click(screen.getByRole("button", { name: /edit/i }))
    expect(onOpenChange).toHaveBeenCalledWith(false)
    expect(mockPush).toHaveBeenCalledWith("/events/e1/edit")
  })

  it("shows the RSVP panel only when the event type allows signups", () => {
    const { unmount } = render(
      <EventDetailSheet event={makeEvent()} open={true} onOpenChange={vi.fn()} />,
    )
    expect(screen.getByTestId("rsvp-panel")).toBeInTheDocument()
    unmount()

    render(
      <EventDetailSheet
        event={makeEvent({ event_type: makeEventType({ allow_signups: false }) })}
        open={true}
        onOpenChange={vi.fn()}
      />,
    )
    expect(screen.queryByTestId("rsvp-panel")).not.toBeInTheDocument()
  })

  it("renders tour-permit status only when applicable", () => {
    const { unmount } = render(
      <EventDetailSheet
        event={makeEvent({ tour_permit_submitted: false })}
        open={true}
        onOpenChange={vi.fn()}
      />,
    )
    expect(screen.getByText("Not submitted")).toBeInTheDocument()
    unmount()

    render(
      <EventDetailSheet
        event={makeEvent({ tour_permit_submitted: null })}
        open={true}
        onOpenChange={vi.fn()}
      />,
    )
    expect(screen.queryByText("Tour permit")).not.toBeInTheDocument()
  })

  it("renders activity metrics when present", () => {
    render(
      <EventDetailSheet
        event={makeEvent({ camping_nights: 2, hiking_miles: "5.0" })}
        open={true}
        onOpenChange={vi.fn()}
      />,
    )
    expect(screen.getByText("Camping nights")).toBeInTheDocument()
    expect(screen.getByText("Hiking miles")).toBeInTheDocument()
  })
})
