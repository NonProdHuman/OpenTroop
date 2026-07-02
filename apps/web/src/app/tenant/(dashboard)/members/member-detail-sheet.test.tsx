/* eslint-disable @typescript-eslint/no-explicit-any */
import React from "react"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { MemberDetailSheet } from "./member-detail-sheet"
import * as memberPositionsHook from "@/hooks/use-member-positions"
import * as positionsHook from "@/hooks/use-positions"
import * as membersHook from "@/hooks/use-members"
import * as sessionHook from "@/hooks/use-session"
import type { Member, MemberPositionAssignment, Position } from "@/types/api"

const mockPush = vi.fn()

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}))

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

vi.mock("@/hooks/use-member-positions", () => ({
  useMemberPositions: vi.fn(),
  useAssignMemberPosition: vi.fn(),
  useUpdateMemberPositionTerm: vi.fn(),
  useRemoveMemberPosition: vi.fn(),
}))

vi.mock("@/hooks/use-positions", () => ({
  usePositions: vi.fn(),
}))

vi.mock("@/hooks/use-members", () => ({
  useMembers: vi.fn(),
  useUpdateMember: vi.fn(),
  useInviteMember: vi.fn(),
}))

vi.mock("@/hooks/use-session", () => ({
  usePermissions: vi.fn(),
}))

function makeMember(overrides: Partial<Member> = {}): Member {
  return {
    id: "m1",
    tenant_id: "t1",
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
    is_deleted: false,
    bsa_id: null,
    first_name: "Alice",
    middle_name: null,
    last_name: "Smith",
    name_suffix: null,
    nickname: null,
    date_of_birth: null,
    email: "alice@example.com",
    phone: null,
    address_line1: null,
    address_line2: null,
    city: null,
    state: null,
    postal_code: null,
    country: null,
    member_type: "scout",
    membership_status: "active",
    swim_classification: "swimmer",
    troop_membership_start_date: null,
    troop_membership_end_date: null,
    swim_date: null,
    medical_form_ab_date: null,
    medical_form_c_date: null,
    allergies: null,
    dietary_restrictions: null,
    emergency_contact_1_name: null,
    emergency_contact_1_phone: null,
    emergency_contact_2_name: null,
    emergency_contact_2_phone: null,
    email_opt_out: false,
    email_bounced: false,
    sms_opt_in: false,
    notes: null,
    oa_member: false,
    oa_active: false,
    oa_election_date: null,
    oa_call_out_date: null,
    oa_ordeal_date: null,
    oa_brotherhood_date: null,
    oa_vigil_date: null,
    oa_vigil_name: null,
    oa_notes: null,
    user_id: null,
    ...overrides,
  }
}

const makePosition = (overrides: Partial<Position>): Position => ({
  id: "p1",
  tenant_id: "t1",
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
  is_deleted: false,
  name: "Patrol Leader",
  slug: "patrol-leader",
  applies_to: "scout",
  sort_order: 10,
  is_system: false,
  is_default: false,
  ...overrides,
})

const makeAssignment = (
  overrides: Partial<MemberPositionAssignment>,
): MemberPositionAssignment => ({
  id: "a1",
  tenant_id: "t1",
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
  is_deleted: false,
  member_id: "m1",
  position_id: "p1",
  assigned_by_id: null,
  start_date: "2024-01-01",
  end_date: null,
  is_current: true,
  ...overrides,
})

describe("MemberDetailSheet", () => {
  const mockUpdateMember = vi.fn()
  const mockInvite = vi.fn()

  function setPositions(assignments: MemberPositionAssignment[], positions: Position[]) {
    vi.mocked(memberPositionsHook.useMemberPositions).mockReturnValue({
      data: assignments,
    } as any)
    vi.mocked(positionsHook.usePositions).mockReturnValue({ data: positions } as any)
  }

  beforeEach(() => {
    vi.clearAllMocks()

    setPositions([], [])
    vi.mocked(memberPositionsHook.useAssignMemberPosition).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
      isError: false,
    } as any)
    vi.mocked(memberPositionsHook.useUpdateMemberPositionTerm).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
      isError: false,
    } as any)
    vi.mocked(memberPositionsHook.useRemoveMemberPosition).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as any)

    vi.mocked(membersHook.useMembers).mockReturnValue({ data: [] } as any)
    vi.mocked(membersHook.useUpdateMember).mockReturnValue({
      mutate: mockUpdateMember,
      isPending: false,
    } as any)
    vi.mocked(membersHook.useInviteMember).mockReturnValue({
      mutate: mockInvite,
      isPending: false,
      isSuccess: false,
      data: undefined,
    } as any)

    vi.mocked(sessionHook.usePermissions).mockReturnValue({
      has: () => false,
      isMember: true,
      isLoading: false,
    } as any)
  })

  it("renders member name and contact details", () => {
    render(<MemberDetailSheet member={makeMember()} open={true} onOpenChange={vi.fn()} />)

    expect(screen.getByText("Alice Smith")).toBeInTheDocument()
    expect(screen.getByText("alice@example.com")).toBeInTheDocument()
    expect(screen.getByText("Scout")).toBeInTheDocument()
  })

  it("renders nothing when member is null", () => {
    const { container } = render(
      <MemberDetailSheet member={null} open={true} onOpenChange={vi.fn()} />,
    )
    expect(container).toBeEmptyDOMElement()
  })

  it("shows the Positions section first with current-position badges", () => {
    setPositions(
      [makeAssignment({})],
      [makePosition({})],
    )

    render(<MemberDetailSheet member={makeMember()} open={true} onOpenChange={vi.fn()} />)

    const headings = screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent)
    expect(headings[0]).toBe("Positions")
    expect(screen.getByText("Patrol Leader")).toBeInTheDocument()
  })

  it("hides the Positions section when the member has no assignments", () => {
    render(<MemberDetailSheet member={makeMember()} open={true} onOpenChange={vi.fn()} />)
    expect(screen.queryByText("Positions")).not.toBeInTheDocument()
  })

  it("renders positions read-only without role:assign", () => {
    setPositions([makeAssignment({})], [makePosition({})])

    render(<MemberDetailSheet member={makeMember()} open={true} onOpenChange={vi.fn()} />)
    expect(screen.queryByRole("button", { name: /add position/i })).not.toBeInTheDocument()
  })

  it("offers position management with role:assign", () => {
    setPositions([makeAssignment({})], [makePosition({})])
    vi.mocked(sessionHook.usePermissions).mockReturnValue({
      has: (p: string) => p === "role:assign",
      isMember: true,
      isLoading: false,
    } as any)

    render(<MemberDetailSheet member={makeMember()} open={true} onOpenChange={vi.fn()} />)
    expect(screen.getByRole("button", { name: /add position/i })).toBeInTheDocument()
  })

  it("navigates to the edit page from the Edit button", async () => {
    const onOpenChange = vi.fn()
    render(<MemberDetailSheet member={makeMember()} open={true} onOpenChange={onOpenChange} />)

    await userEvent.click(screen.getByRole("button", { name: /edit/i }))
    expect(onOpenChange).toHaveBeenCalledWith(false)
    expect(mockPush).toHaveBeenCalledWith("/members/m1/edit")
  })

  it("deactivates an active member", async () => {
    render(<MemberDetailSheet member={makeMember()} open={true} onOpenChange={vi.fn()} />)

    await userEvent.click(screen.getByRole("button", { name: /deactivate/i }))
    expect(mockUpdateMember).toHaveBeenCalledWith({
      id: "m1",
      data: { membership_status: "inactive" },
    })
  })

  it("reactivates an inactive member", async () => {
    render(
      <MemberDetailSheet
        member={makeMember({ membership_status: "inactive" })}
        open={true}
        onOpenChange={vi.fn()}
      />,
    )

    await userEvent.click(screen.getByRole("button", { name: /reactivate/i }))
    expect(mockUpdateMember).toHaveBeenCalledWith({
      id: "m1",
      data: { membership_status: "active" },
    })
  })

  it("copies the claim link when the invite email could not be sent", async () => {
    vi.mocked(membersHook.useInviteMember).mockReturnValue({
      mutate: mockInvite,
      isPending: false,
      isSuccess: true,
      data: { token: "tok123", email_sent: false },
    } as any)
    const writeText = vi.fn().mockResolvedValue(undefined)
    vi.stubGlobal("navigator", { ...navigator, clipboard: { writeText } })

    render(<MemberDetailSheet member={makeMember()} open={true} onOpenChange={vi.fn()} />)

    expect(screen.getByText(/couldn't email this invite/i)).toBeInTheDocument()
    await userEvent.click(screen.getByRole("button", { name: /copy link/i }))
    expect(writeText).toHaveBeenCalledWith(expect.stringContaining("/claim?token=tok123"))
    expect(await screen.findByRole("button", { name: /copied/i })).toBeInTheDocument()
  })

  it("offers Send Invite only for unclaimed members", async () => {
    const { unmount } = render(
      <MemberDetailSheet member={makeMember({ user_id: null })} open={true} onOpenChange={vi.fn()} />,
    )
    await userEvent.click(screen.getByRole("button", { name: /send invite/i }))
    expect(mockInvite).toHaveBeenCalledWith("m1")
    unmount()

    render(
      <MemberDetailSheet
        member={makeMember({ user_id: "u1" })}
        open={true}
        onOpenChange={vi.fn()}
      />,
    )
    expect(screen.queryByRole("button", { name: /send invite/i })).not.toBeInTheDocument()
  })
})
