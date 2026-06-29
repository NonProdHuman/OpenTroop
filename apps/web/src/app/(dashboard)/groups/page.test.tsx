/* eslint-disable @typescript-eslint/no-explicit-any */
import React from "react"
import { render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import GroupsPage from "./page"
import * as groupsHook from "@/hooks/use-groups"
import * as membersHook from "@/hooks/use-members"
import type { Group, Member } from "@/types/api"

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

vi.mock("./group-detail-sheet", () => ({
  GroupDetailSheet: () => <div data-testid="detail-sheet">Detail Sheet</div>,
}))

// Mock DropdownMenu to render inline during tests
vi.mock("@/components/ui/dropdown-menu", () => ({
  DropdownMenu: ({ children }: any) => <div>{children}</div>,
  DropdownMenuTrigger: ({ children, render }: any) => {
    if (render) {
      return render
    }
    return <button type="button">{children}</button>
  },
  DropdownMenuPortal: ({ children }: any) => children,
  DropdownMenuContent: ({ children }: any) => <div data-testid="dropdown-content">{children}</div>,
  DropdownMenuItem: ({ children, ...props }: any) => <button type="button" {...props}>{children}</button>,
  DropdownMenuSeparator: () => <hr />,
}))

vi.mock("@/hooks/use-groups", () => ({
  useGroups: vi.fn(),
  useGroupMemberCounts: vi.fn(() => new Map()),
  useAddGroupMember: vi.fn(),
  useGroupMembers: vi.fn(),
  useDeleteGroup: vi.fn(),
}))

vi.mock("@/hooks/use-members", () => ({
  useMembers: vi.fn(),
}))

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

describe("GroupsPage", () => {
  const mockAdd = vi.fn()
  const mockDelete = vi.fn()

  const mockGroups: Group[] = [
    {
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
    },
    {
      id: "g2",
      tenant_id: "t1",
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T00:00:00Z",
      is_deleted: false,
      name: "Super Admins",
      group_type: "custom",
      is_system: true,
      color: null,
      description: "System group",
      rule_logic: "and",
      include_parents: false,
      cc_parents_on_messages: false,
    }
  ]

  const mockAllMembers: Member[] = [
    {
      id: "m1",
      tenant_id: "t1",
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T00:00:00Z",
      is_deleted: false,
      first_name: "Alice",
      last_name: "Smith",
      nickname: null,
      email: "alice@example.com",
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

    vi.mocked(groupsHook.useGroups).mockReturnValue({
      data: mockGroups,
      isLoading: false,
    } as any)

    vi.mocked(groupsHook.useGroupMembers).mockReturnValue({
      data: [],
      isLoading: false,
    } as any)

    vi.mocked(groupsHook.useAddGroupMember).mockReturnValue({
      mutate: mockAdd,
      isPending: false,
    } as any)

    vi.mocked(groupsHook.useDeleteGroup).mockReturnValue({
      mutate: mockDelete,
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

  it("renders the list of groups", () => {
    render(<GroupsPage />)

    expect(screen.getByText("Patrol Alpha")).toBeInTheDocument()
    expect(screen.getByText("Super Admins")).toBeInTheDocument()
  })

  it("opens actions dropdown and launches Add Member dialog", async () => {
    render(<GroupsPage />)

    // Find the non-system row action button (MoreHorizontal)
    const row = screen.getByText("Patrol Alpha").closest("tr")
    expect(row).toBeDefined()

    if (row) {
      const actionBtn = within(row).getByRole("button", { name: /actions/i })
      expect(actionBtn).toBeInTheDocument()

      await userEvent.click(actionBtn)

      // Verify dropdown options are rendered (mock menu renders items directly)
      const addOption = screen.getByRole("button", { name: /add member…/i })
      expect(addOption).toBeInTheDocument()

      await userEvent.click(addOption)

      // Dialog should open
      expect(screen.getByRole("heading", { name: "Add Member to Patrol Alpha" })).toBeInTheDocument()

      const aliceOption = screen.getByText("Alice Smith")
      expect(aliceOption).toBeInTheDocument()

      await userEvent.click(aliceOption)

      expect(mockAdd).toHaveBeenCalledWith(
        { groupId: "g1", memberId: "m1" },
        expect.any(Object)
      )
    }
  })

  it("does not render actions dropdown button for system groups", () => {
    render(<GroupsPage />)

    const row = screen.getByText("Super Admins").closest("tr")
    expect(row).toBeDefined()

    if (row) {
      expect(within(row).queryByRole("button", { name: /actions/i })).not.toBeInTheDocument()
      expect(within(row).getByTitle("System group")).toBeInTheDocument()
    }
  })
})
