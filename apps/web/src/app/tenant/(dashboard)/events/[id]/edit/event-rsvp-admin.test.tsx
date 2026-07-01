import { render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { EventRsvpAdmin } from "./event-rsvp-admin"
import type { Event, Member } from "@/types/api"

const addMutate = vi.fn()
const updateMutate = vi.fn()

let audiences: { id: string; group_id: string }[] = []
let participants: { id: string; member_id: string; rsvp_status: string; driver?: boolean }[] = []
let groupsByMember = new Map<string, { id: string; name: string }[]>()
let patrolByMember = new Map<string, { id: string; name: string }>()

vi.mock("@/hooks/use-events", () => ({
  useEventAudiences: () => ({ data: audiences }),
  useEventParticipants: () => ({ data: participants }),
  useAddParticipant: () => ({ mutate: addMutate }),
  useUpdateParticipant: () => ({ mutate: updateMutate }),
}))

const members: Partial<Member>[] = [
  { id: "m-scout", first_name: "Sam", last_name: "Scout", member_type: "scout", membership_status: "active", is_deleted: false },
  { id: "m-adult", first_name: "Pat", last_name: "Parent", member_type: "adult", membership_status: "active", is_deleted: false },
  { id: "m-inactive", first_name: "Old", last_name: "Member", member_type: "scout", membership_status: "inactive", is_deleted: false },
]

vi.mock("@/hooks/use-members", () => ({
  useMembers: () => ({ data: members }),
}))

vi.mock("@/hooks/use-groups", () => ({
  useGroupMemberships: () => groupsByMember,
  usePatrolMemberships: () => patrolByMember,
}))

const event = { id: "event-1" } as Event

describe("EventRsvpAdmin", () => {
  beforeEach(() => {
    addMutate.mockReset()
    updateMutate.mockReset()
    audiences = []
    participants = []
    groupsByMember = new Map()
    patrolByMember = new Map()
  })

  it("shows all active members when there are no audiences", () => {
    render(<EventRsvpAdmin event={event} />)
    expect(screen.getByText("Sam Scout")).toBeInTheDocument()
    expect(screen.getByText("Pat Parent")).toBeInTheDocument()
    // Inactive members are excluded from the roster.
    expect(screen.queryByText("Old Member")).not.toBeInTheDocument()
  })

  it("scopes the roster to audience-group members", () => {
    audiences = [{ id: "a1", group_id: "g1" }]
    groupsByMember = new Map([["m-scout", [{ id: "g1", name: "Patrol A" }]]])
    render(<EventRsvpAdmin event={event} />)
    expect(screen.getByText("Sam Scout")).toBeInTheDocument()
    // Pat is not in any audience group.
    expect(screen.queryByText("Pat Parent")).not.toBeInTheDocument()
  })

  function rowFor(name: string): HTMLElement {
    return screen.getByText(name).closest("div.rounded-md") as HTMLElement
  }

  it("creates a participant row when setting Going for a member with no RSVP", async () => {
    render(<EventRsvpAdmin event={event} />)
    await userEvent.click(within(rowFor("Sam Scout")).getByRole("button", { name: "Going" }))
    expect(addMutate).toHaveBeenCalledTimes(1)
    expect(addMutate.mock.calls[0][0]).toMatchObject({
      member_id: "m-scout",
      rsvp_status: "going",
    })
  })

  it("PATCHes an existing participant when changing RSVP", async () => {
    participants = [{ id: "p1", member_id: "m-scout", rsvp_status: "no_response" }]
    render(<EventRsvpAdmin event={event} />)
    await userEvent.click(within(rowFor("Sam Scout")).getByRole("button", { name: "Declined" }))
    expect(updateMutate).toHaveBeenCalledTimes(1)
    expect(updateMutate.mock.calls[0][0]).toMatchObject({
      memberId: "m-scout",
      rsvp_status: "declined",
    })
  })

  it("filters the roster by member type", async () => {
    render(<EventRsvpAdmin event={event} />)
    await userEvent.click(screen.getByRole("button", { name: "Adults" }))
    expect(screen.getByText("Pat Parent")).toBeInTheDocument()
    expect(screen.queryByText("Sam Scout")).not.toBeInTheDocument()
  })

  it("filters to drivers only", async () => {
    participants = [{ id: "p1", member_id: "m-adult", rsvp_status: "going", driver: true }]
    render(<EventRsvpAdmin event={event} />)
    await userEvent.click(screen.getByRole("button", { name: "Drivers" }))
    expect(screen.getByText("Pat Parent")).toBeInTheDocument()
    expect(screen.queryByText("Sam Scout")).not.toBeInTheDocument()
  })
})
