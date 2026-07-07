import React from "react"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { FamilyEvents } from "./family-events"
import { makeEvent, makeMember } from "./test-helpers"

const addMutate = vi.fn()
const updateMutate = vi.fn()

// Mock the whole events hook module: FamilyEvents uses useEvents, and the reused
// EventRsvpPanel → MemberRsvpRow → useRsvpDraft all draw their participant hooks
// from here, so one mock covers the whole quick-RSVP path.
vi.mock("@/hooks/use-events", () => ({
  useEvents: vi.fn(),
  useEventParticipants: () => ({ data: [] }),
  useAddParticipant: () => ({ mutate: addMutate }),
  useUpdateParticipant: () => ({ mutate: updateMutate }),
  useGrantPermission: () => ({ mutate: vi.fn() }),
}))

vi.mock("@/hooks/use-session", () => ({
  useSession: () => ({ data: { member: makeMember({ id: "self", member_type: "adult" }) } }),
}))
vi.mock("@/hooks/use-relationships", () => ({ useRelationships: () => ({ data: [] }) }))
vi.mock("@/hooks/use-members", () => ({
  useMembers: () => ({ data: [makeMember({ id: "self", first_name: "Pat", member_type: "adult" })] }),
}))
vi.mock("@/hooks/use-tenant-settings", () => ({ useTenantSettings: () => ({ data: {} }) }))

import { useEvents } from "@/hooks/use-events"
const mockUseEvents = useEvents as unknown as ReturnType<typeof vi.fn>

describe("FamilyEvents", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("shows an empty state when there are no upcoming events", () => {
    mockUseEvents.mockReturnValue({ data: [], isLoading: false })
    render(<FamilyEvents />)
    expect(screen.getByText(/no upcoming events/i)).toBeInTheDocument()
  })

  it("renders the reused RSVP panel and a quick RSVP fires the existing participant mutation", async () => {
    mockUseEvents.mockReturnValue({ data: [makeEvent()], isLoading: false })
    render(<FamilyEvents />)

    expect(screen.getByTestId("family-event")).toBeInTheDocument()
    // The quick RSVP control comes straight from the event page (rsvp-controls).
    await userEvent.click(screen.getByTestId("rsvp-going"))
    expect(addMutate).toHaveBeenCalledTimes(1)
    expect(addMutate).toHaveBeenCalledWith(
      expect.objectContaining({ member_id: "self", rsvp_status: "going" }),
    )
  })

  it("hides past events", () => {
    mockUseEvents.mockReturnValue({
      data: [makeEvent({ scheduled_start: "2000-01-01T00:00:00Z", scheduled_end: "2000-01-02T00:00:00Z" })],
      isLoading: false,
    })
    render(<FamilyEvents />)
    expect(screen.getByText(/no upcoming events/i)).toBeInTheDocument()
  })
})
