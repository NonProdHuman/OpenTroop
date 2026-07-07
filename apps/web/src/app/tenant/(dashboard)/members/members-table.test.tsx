import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MembersTable } from "./members-table"
import { buildColumns } from "./columns"
import type { Member, Group } from "@/types/api"

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
    announcement_email_mode: "every",
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

describe("MembersTable", () => {
  const columns = buildColumns(new Map<string, Group[]>(), new Map())

  it("renders member rows", () => {
    render(
      <MembersTable
        data={[makeMember()]}
        columns={columns}
        isLoading={false}
        onRowClick={vi.fn()}
      />,
    )
    expect(screen.getByText("Alice Smith")).toBeInTheDocument()
    expect(screen.getByText("alice@example.com")).toBeInTheDocument()
  })

  it("shows skeletons while loading", () => {
    const { container } = render(
      <MembersTable
        data={[]}
        columns={columns}
        isLoading={true}
        onRowClick={vi.fn()}
      />,
    )
    expect(container.querySelectorAll(".animate-pulse")).toHaveLength(8)
  })

  it("shows empty state when no data", () => {
    render(
      <MembersTable
        data={[]}
        columns={columns}
        isLoading={false}
        onRowClick={vi.fn()}
      />,
    )
    expect(
      screen.getByText("No members match your filters."),
    ).toBeInTheDocument()
  })

  it("calls onRowClick when a row is clicked", async () => {
    const onRowClick = vi.fn()
    const member = makeMember()
    render(
      <MembersTable
        data={[member]}
        columns={columns}
        isLoading={false}
        onRowClick={onRowClick}
      />,
    )
    await userEvent.click(screen.getByText("Alice Smith"))
    expect(onRowClick).toHaveBeenCalledWith(member)
  })

  it("renders member group bubbles", () => {
    const testGroup: Group = {
      id: "g1",
      tenant_id: "t1",
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T00:00:00Z",
      is_deleted: false,
      name: "Fox Patrol",
      description: null,
      group_type: "patrol",
      color: null,
      is_system: false,
      rule_logic: "and",
      include_parents: false,
      cc_parents_on_messages: false,
    }
    const testGroup2: Group = {
      id: "g2",
      tenant_id: "t1",
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T00:00:00Z",
      is_deleted: false,
      name: "Leadership",
      description: null,
      group_type: "custom",
      color: null,
      is_system: false,
      rule_logic: "and",
      include_parents: false,
      cc_parents_on_messages: false,
    }
    const groupMap = new Map<string, Group[]>([["m1", [testGroup, testGroup2]]])
    const columnsWithGroups = buildColumns(groupMap, new Map())
    render(
      <MembersTable
        data={[makeMember({ id: "m1" })]}
        columns={columnsWithGroups}
        isLoading={false}
        onRowClick={vi.fn()}
      />,
    )
    expect(screen.getByText("Fox Patrol")).toBeInTheDocument()
    expect(screen.getByText("Leadership")).toBeInTheDocument()
  })
})
