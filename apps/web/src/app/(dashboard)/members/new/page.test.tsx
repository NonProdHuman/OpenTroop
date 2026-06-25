import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import NewMemberPage from "./page"

const push = vi.fn()
const mutate = vi.fn()

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}))

vi.mock("@/components/page-header", () => ({
  PageHeader: ({ title, children }: { title: string; children?: React.ReactNode }) => (
    <div>
      <h1>{title}</h1>
      {children}
    </div>
  ),
}))

vi.mock("@/hooks/use-members", () => ({
  useCreateMember: () => ({ mutate, isPending: false }),
}))

describe("NewMemberPage", () => {
  beforeEach(() => {
    push.mockReset()
    mutate.mockReset()
  })

  it("blocks submit and shows an error when names are empty", async () => {
    render(<NewMemberPage />)
    await userEvent.click(screen.getAllByRole("button", { name: /create member/i })[0])
    expect(screen.getByText("First name and last name are required.")).toBeInTheDocument()
    expect(mutate).not.toHaveBeenCalled()
  })

  it("submits a valid member and navigates to the list", async () => {
    mutate.mockImplementation((_payload, opts) => opts?.onSuccess?.())
    render(<NewMemberPage />)

    // First two text inputs are First name and Last name (date/select/number
    // fields don't carry the textbox role).
    const textboxes = screen.getAllByRole("textbox")
    await userEvent.type(textboxes[0], "Alice")
    await userEvent.type(textboxes[1], "Smith")
    await userEvent.click(screen.getAllByRole("button", { name: /create member/i })[0])

    expect(mutate).toHaveBeenCalledTimes(1)
    const payload = mutate.mock.calls[0][0]
    expect(payload).toMatchObject({
      first_name: "Alice",
      last_name: "Smith",
      member_type: "scout",
      membership_status: "active",
      country: "US",
    })
    expect(push).toHaveBeenCalledWith("/members")
  })
})
