import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { PageHeader } from "./page-header"

// SidebarTrigger needs SidebarContext — mock it since its behavior
// is not under test here.
vi.mock("@/components/ui/sidebar", () => ({
  SidebarTrigger: () => <button aria-label="Toggle sidebar" />,
}))

vi.mock("@/components/ui/separator", () => ({
  Separator: () => <hr />,
}))

describe("PageHeader", () => {
  it("renders the page title", () => {
    render(<PageHeader title="Members" />)
    expect(screen.getByText("Members")).toBeInTheDocument()
  })

  it("renders without an action area when no children provided", () => {
    render(<PageHeader title="Members" />)
    // Should not throw; just the title + trigger
    expect(screen.queryByRole("button", { name: /add/i })).toBeNull()
  })

  it("renders children in the action area", () => {
    render(
      <PageHeader title="Members">
        <button>Add Member</button>
      </PageHeader>,
    )
    expect(screen.getByRole("button", { name: "Add Member" })).toBeInTheDocument()
  })

  it("includes the sidebar toggle trigger", () => {
    render(<PageHeader title="Events" />)
    expect(screen.getByRole("button", { name: "Toggle sidebar" })).toBeInTheDocument()
  })
})
