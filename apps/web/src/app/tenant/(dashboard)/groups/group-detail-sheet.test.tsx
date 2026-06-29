/* eslint-disable @typescript-eslint/no-explicit-any */
import React from "react"
import { render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { GroupDetailSheet } from "./group-detail-sheet"
import * as groupsHook from "@/hooks/use-groups"
import * as membersHook from "@/hooks/use-members"
import type { Group, Member } from "@/types/api"

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}))

// Mock Popover to render inline during tests
vi.mock("@/components/ui/popover", () => ({
  Popover: ({ children }: any) => <div>{children}</div>,
  PopoverTrigger: ({ children, ...props }: any) => <button type="button" {...props}>{children}</button>,
  PopoverContent: ({ children }: any) => <div data-testid="popover-content">{children}</div>,
}))

vi.mock("@/hooks/use-groups", () => ({
  useGroupMembers: vi.fn(),
  useGroupManualMembers: vi.fn(),
  useGroupRules: vi.fn(),
  useDeleteGroup: vi.fn(),
  useAddGroupMember: vi.fn(),
  useRemoveGroupMember: vi.fn(),
  useGroups: vi.fn(),
}))

vi.mock("@/hooks/use-members", () => ({
  useMembers: vi.fn(),
}))

vi.mock("@/hooks/use-positions", () => ({
  usePositions: vi.fn(() => ({ data: [] })),
}))

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

describe("GroupDetailSheet", () => {
  const mockAdd = vi.fn()
  const mockRemove = vi.fn()

  const mockGroup: Group = {
    id: "g1",
    tenant_id: "t1",
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
    is_deleted: false,
    name: "Patrol Alpha",
    group_type: "patrol",
    is_system: false,
    color: "#F59E0B",
    description: "Alpha patrol description",
    rule_logic: "and",
      include_parents: false,
      cc_parents_on_messages: false,
  }

  const mockGroupMembers: Member[] = [
    {
      id: "m1",
      tenant_id: "t1",
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T00:00:00Z",
      is_deleted: false,
      first_name: "John",
      last_name: "Doe",
      nickname: "Johnny",
      email: "john@example.com",
      member_type: "scout",
      membership_status: "active",
      swim_classification: "swimmer",
      troop_membership_start_date: null,
      troop_membership_end_date: null,
      bsa_id: null,
      middle_name: null,
      name_suffix: null,
      date_of_birth: null,
      phone: null,
      address_line1: null,
      address_line2: null,
      city: null,
      state: null,
      postal_code: null,
      country: null,
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
    }
  ]

  const mockAllMembers: Member[] = [
    ...mockGroupMembers,
    {
      id: "m2",
      tenant_id: "t1",
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T00:00:00Z",
      is_deleted: false,
      first_name: "Jane",
      last_name: "Smith",
      nickname: null,
      email: "jane@example.com",
      member_type: "scout",
      membership_status: "active",
      swim_classification: "swimmer",
      troop_membership_start_date: null,
      troop_membership_end_date: null,
      bsa_id: null,
      middle_name: null,
      name_suffix: null,
      date_of_birth: null,
      phone: null,
      address_line1: null,
      address_line2: null,
      city: null,
      state: null,
      postal_code: null,
      country: null,
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
    }
  ]

  beforeEach(() => {
    vi.clearAllMocks()

    vi.mocked(groupsHook.useGroupMembers).mockReturnValue({
      data: mockGroupMembers,
      isLoading: false,
    } as any)

    // m1 is a manual member (so its remove "×" shows).
    vi.mocked(groupsHook.useGroupManualMembers).mockReturnValue({
      data: mockGroupMembers.map((m) => ({ member_id: m.id })),
    } as any)

    vi.mocked(groupsHook.useGroupRules).mockReturnValue({
      data: [],
    } as any)
    vi.mocked(groupsHook.useGroups).mockReturnValue({
      data: [mockGroup],
    } as any)

    vi.mocked(groupsHook.useDeleteGroup).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as any)

    vi.mocked(groupsHook.useAddGroupMember).mockReturnValue({
      mutate: mockAdd,
      isPending: false,
    } as any)

    vi.mocked(groupsHook.useRemoveGroupMember).mockReturnValue({
      mutate: mockRemove,
      isPending: false,
    } as any)

    vi.mocked(membersHook.useMembers).mockReturnValue({
      data: mockAllMembers,
    } as any)

    // Mock ResizeObserver globally to satisfy cmdk
    class MockResizeObserver {
      observe = vi.fn()
      unobserve = vi.fn()
      disconnect = vi.fn()
    }
    vi.stubGlobal("ResizeObserver", MockResizeObserver)
    window.HTMLElement.prototype.scrollIntoView = vi.fn()
  })

  it("renders group information and member list", () => {
    render(<GroupDetailSheet group={mockGroup} open={true} onOpenChange={vi.fn()} />)

    expect(screen.getByText("Patrol Alpha")).toBeInTheDocument()
    expect(screen.getByText("Alpha patrol description")).toBeInTheDocument()
    expect(screen.getByText("John \"Johnny\" Doe")).toBeInTheDocument()
  })

  it("triggers removeMember mutation when remove button is clicked", async () => {
    render(<GroupDetailSheet group={mockGroup} open={true} onOpenChange={vi.fn()} />)

    const removeBtn = screen.getByRole("button", { name: /remove john \"johnny\" doe/i })
    expect(removeBtn).toBeInTheDocument()

    await userEvent.click(removeBtn)
    expect(mockRemove).toHaveBeenCalledWith(
      { groupId: "g1", memberId: "m1" },
      expect.any(Object)
    )
  })

  it("opens add member popover and triggers addMember mutation", async () => {
    render(<GroupDetailSheet group={mockGroup} open={true} onOpenChange={vi.fn()} />)

    const addBtn = screen.getByRole("button", { name: /add member/i })
    expect(addBtn).toBeInTheDocument()

    await userEvent.click(addBtn)

    // Verify popover command menu is shown
    const searchInput = screen.getByPlaceholderText("Search members…")
    expect(searchInput).toBeInTheDocument()

    // Jane Smith should be in the list of addable members (John Doe is already a member)
    const popoverContent = screen.getByTestId("popover-content")
    const janeOption = within(popoverContent).getByText("Jane Smith")
    expect(janeOption).toBeInTheDocument()
    expect(within(popoverContent).queryByText("John \"Johnny\" Doe")).not.toBeInTheDocument()

    await userEvent.click(janeOption)

    expect(mockAdd).toHaveBeenCalledWith(
      { groupId: "g1", memberId: "m2" },
      expect.any(Object)
    )
  })
})
