/* eslint-disable @typescript-eslint/no-explicit-any */
import React from "react"
import { render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import EventTypesPage from "./page"
import * as eventsHook from "@/hooks/use-events"
import * as sessionHook from "@/hooks/use-session"
import type { EventType } from "@/types/api"

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}))

vi.mock("@/components/page-header", () => ({
  PageHeader: ({ title, children }: { title: string; children?: React.ReactNode }) => (
    <div>
      <h1>{title}</h1>
      {children}
    </div>
  ),
}))

vi.mock("@/hooks/use-events", () => ({
  useEventTypes: vi.fn(),
}))

vi.mock("@/hooks/use-session", () => ({
  usePermissions: vi.fn(),
}))

const makeType = (overrides: Partial<EventType>): EventType => ({
  id: "et1",
  tenant_id: "t1",
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
  is_deleted: false,
  name: "Campout",
  color: "#3b82f6",
  is_active: true,
  is_online: false,
  is_system: false,
  allow_guests: false,
  allow_signups: true,
  require_permission_slip: false,
  tracks_service_hours: false,
  tracks_camping_nights: false,
  tracks_mileage: false,
  ...overrides,
})

describe("EventTypesPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(eventsHook.useEventTypes).mockReturnValue({ data: [], isLoading: false } as any)
    vi.mocked(sessionHook.usePermissions).mockReturnValue({
      has: () => true,
      isMember: true,
      isLoading: false,
    } as any)
  })

  it("renders the page header", () => {
    render(<EventTypesPage />)
    expect(screen.getByRole("heading", { name: "Event Types" })).toBeInTheDocument()
  })

  it("shows the empty state when there are no event types", () => {
    render(<EventTypesPage />)
    expect(screen.getByText("No event types yet.")).toBeInTheDocument()
  })

  it("shows 'New event type' when the user has event:write", () => {
    vi.mocked(eventsHook.useEventTypes).mockReturnValue({
      data: [makeType({})],
      isLoading: false,
    } as any)
    vi.mocked(sessionHook.usePermissions).mockReturnValue({
      has: (p: string) => p === "event:write",
      isMember: true,
      isLoading: false,
    } as any)
    render(<EventTypesPage />)
    expect(screen.getByRole("button", { name: /new event type/i })).toBeInTheDocument()
  })

  it("hides 'New event type' when the user lacks event:write", () => {
    vi.mocked(eventsHook.useEventTypes).mockReturnValue({
      data: [makeType({})],
      isLoading: false,
    } as any)
    vi.mocked(sessionHook.usePermissions).mockReturnValue({
      has: () => false,
      isMember: true,
      isLoading: false,
    } as any)
    render(<EventTypesPage />)
    expect(screen.queryByRole("button", { name: /new event type/i })).not.toBeInTheDocument()
  })

  it("renders types with capability badges and a system lock", () => {
    vi.mocked(eventsHook.useEventTypes).mockReturnValue({
      data: [
        makeType({ id: "et1", name: "Campout", allow_signups: true, tracks_camping_nights: true }),
        makeType({ id: "et2", name: "Meeting", is_system: true, allow_signups: false }),
      ],
      isLoading: false,
    } as any)
    render(<EventTypesPage />)
    expect(screen.getByText("Campout")).toBeInTheDocument()
    expect(screen.getByText("Meeting")).toBeInTheDocument()
    expect(screen.getByText("Sign-ups")).toBeInTheDocument()
    expect(screen.getByText("Camping")).toBeInTheDocument()
  })

  it("marks inactive types", () => {
    vi.mocked(eventsHook.useEventTypes).mockReturnValue({
      data: [makeType({ id: "et1", name: "Old Type", is_active: false })],
      isLoading: false,
    } as any)
    render(<EventTypesPage />)
    expect(screen.getByText("Inactive")).toBeInTheDocument()
  })

  it("shows the loading state", () => {
    vi.mocked(eventsHook.useEventTypes).mockReturnValue({ data: undefined, isLoading: true } as any)
    render(<EventTypesPage />)
    expect(screen.getByText("Loading…")).toBeInTheDocument()
  })
})
