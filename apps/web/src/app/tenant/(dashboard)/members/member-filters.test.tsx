import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemberFilters } from "./member-filters"

const defaultProps = {
  search: "",
  types: [] as ("scout" | "adult")[],
  statuses: [] as ("active" | "inactive" | "alumni")[],
  patrolId: null,
  patrols: [],
  onSearchChange: vi.fn(),
  onTypeToggle: vi.fn(),
  onStatusToggle: vi.fn(),
  onPatrolChange: vi.fn(),
  onClear: vi.fn(),
}

describe("MemberFilters", () => {
  it("renders search input and toggle buttons", () => {
    render(<MemberFilters {...defaultProps} />)
    expect(screen.getByPlaceholderText("Search members…")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Scouts" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Adults" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Active" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Inactive" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Alumni" })).toBeInTheDocument()
  })

  it("hides Clear button when nothing is set", () => {
    render(<MemberFilters {...defaultProps} />)
    expect(screen.queryByRole("button", { name: /clear/i })).not.toBeInTheDocument()
  })

  it("shows Clear button when search is active", () => {
    render(<MemberFilters {...defaultProps} search="alice" />)
    expect(screen.getByRole("button", { name: /clear/i })).toBeInTheDocument()
  })

  it("calls onSearchChange when typing", async () => {
    const onSearchChange = vi.fn()
    render(<MemberFilters {...defaultProps} onSearchChange={onSearchChange} />)
    await userEvent.type(screen.getByPlaceholderText("Search members…"), "b")
    expect(onSearchChange).toHaveBeenCalledWith("b")
  })

  it("calls onTypeToggle when Scouts is clicked", async () => {
    const onTypeToggle = vi.fn()
    render(<MemberFilters {...defaultProps} onTypeToggle={onTypeToggle} />)
    await userEvent.click(screen.getByRole("button", { name: "Scouts" }))
    expect(onTypeToggle).toHaveBeenCalledWith("scout")
  })

  it("calls onClear when Clear is clicked", async () => {
    const onClear = vi.fn()
    render(
      <MemberFilters {...defaultProps} search="something" onClear={onClear} />,
    )
    await userEvent.click(screen.getByRole("button", { name: /clear/i }))
    expect(onClear).toHaveBeenCalled()
  })
})
