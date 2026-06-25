import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MembersTable } from "./members-table"
import { buildColumns } from "./columns"
import type { Member } from "@/types/api"

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

describe("MembersTable", () => {
  const columns = buildColumns()

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
})
