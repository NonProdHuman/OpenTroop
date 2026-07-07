/* eslint-disable @typescript-eslint/no-explicit-any */
import React from "react"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { EventSlotsPanel } from "./event-slots-panel"
import * as sessionHook from "@/hooks/use-session"
import * as slotsHook from "@/hooks/use-event-slots"
import * as membersHook from "@/hooks/use-members"
import * as relationshipsHook from "@/hooks/use-relationships"
import type { Event, EventSlot, Member } from "@/types/api"

vi.mock("@/hooks/use-session", () => ({ useSession: vi.fn() }))
vi.mock("@/hooks/use-event-slots", () => ({
  useEventSlots: vi.fn(),
  useJoinSlot: vi.fn(),
  useLeaveSlot: vi.fn(),
}))
vi.mock("@/hooks/use-members", () => ({ useMembers: vi.fn() }))
vi.mock("@/hooks/use-relationships", () => ({ useRelationships: vi.fn() }))

const SELF = "m-self"

const member = (id: string, first: string, member_type: "scout" | "adult"): Member =>
  ({
    id,
    tenant_id: "t1",
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
    is_deleted: false,
    first_name: first,
    last_name: "Test",
    member_type,
  }) as any

const slot = (overrides: Partial<EventSlot> = {}): EventSlot =>
  ({
    id: "s1",
    tenant_id: "t1",
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
    is_deleted: false,
    event_id: "e1",
    name: "Grubmaster",
    description: null,
    capacity: 2,
    applies_to: "any",
    starts_at: null,
    ends_at: null,
    sort_order: 0,
    signups: [],
    remaining: 2,
    ...overrides,
  }) as any

const event = { id: "e1" } as Event

const joinMutate = vi.fn()
const leaveMutate = vi.fn()

function setup(slots: EventSlot[], self: Member | null = member(SELF, "Me", "adult")) {
  vi.mocked(sessionHook.useSession).mockReturnValue({ data: self ? { member: self } : undefined } as any)
  vi.mocked(slotsHook.useEventSlots).mockReturnValue({ data: slots } as any)
  vi.mocked(slotsHook.useJoinSlot).mockReturnValue({ mutate: joinMutate, isPending: false } as any)
  vi.mocked(slotsHook.useLeaveSlot).mockReturnValue({ mutate: leaveMutate, isPending: false } as any)
  vi.mocked(membersHook.useMembers).mockReturnValue({ data: self ? [self] : [] } as any)
  vi.mocked(relationshipsHook.useRelationships).mockReturnValue({ data: [] } as any)
}

describe("EventSlotsPanel", () => {
  beforeEach(() => vi.clearAllMocks())

  it("renders nothing when there are no slots", () => {
    setup([])
    const { container } = render(<EventSlotsPanel event={event} />)
    expect(container).toBeEmptyDOMElement()
  })

  it("shows the fill state and a sign-up button for self", async () => {
    setup([slot()])
    render(<EventSlotsPanel event={event} />)
    expect(screen.getByTestId("slot-fill-s1")).toHaveTextContent("0 of 2")

    await userEvent.click(screen.getByTestId("slot-join-s1-m-self"))
    expect(joinMutate).toHaveBeenCalledWith({ slotId: "s1", memberId: SELF })
  })

  it("shows Leave when already signed up and lists roster names", () => {
    const self = member(SELF, "Me", "adult")
    setup(
      [
        slot({
          signups: [
            {
              id: "su1",
              tenant_id: "t1",
              created_at: "2024-01-01T00:00:00Z",
              updated_at: "2024-01-01T00:00:00Z",
              is_deleted: false,
              slot_id: "s1",
              member_id: SELF,
              member_name: "Me Test",
              comment: null,
              signed_up_by_id: SELF,
              signed_up_at: "2024-01-01T00:00:00Z",
            } as any,
          ],
          remaining: 1,
        }),
      ],
      self,
    )
    render(<EventSlotsPanel event={event} />)
    expect(screen.getByText("Me Test")).toBeInTheDocument()
    expect(screen.getByTestId("slot-leave-s1-m-self")).toBeInTheDocument()
  })

  it("disables sign-up (Full) when capacity is reached", () => {
    setup([slot({ remaining: 0 })])
    render(<EventSlotsPanel event={event} />)
    expect(screen.getByTestId("slot-join-s1-m-self")).toBeDisabled()
  })

  it("hides the sign-up button for an ineligible member type", () => {
    setup([slot({ applies_to: "scout" })], member(SELF, "Me", "adult"))
    render(<EventSlotsPanel event={event} />)
    expect(screen.queryByTestId("slot-join-s1-m-self")).not.toBeInTheDocument()
  })
})
