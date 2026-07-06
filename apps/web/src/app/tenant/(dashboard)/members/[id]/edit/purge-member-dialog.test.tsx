import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import type { Member } from "@/types/api"
import * as membersHook from "@/hooks/use-members"
import { PurgeMemberDialog } from "./purge-member-dialog"

const mockPush = vi.fn()

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}))

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

vi.mock("@/hooks/use-members", () => ({
  usePurgeMember: vi.fn(),
}))

const member = {
  id: "m1",
  first_name: "Alice",
  last_name: "Smith",
} as Member

const mutateAsync = vi.fn().mockResolvedValue(undefined)

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(membersHook.usePurgeMember).mockReturnValue({
    mutateAsync,
    isPending: false,
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
  } as any)
})

describe("PurgeMemberDialog", () => {
  it("keeps the destructive button disarmed until the full name matches", async () => {
    const user = userEvent.setup()
    render(<PurgeMemberDialog member={member} />)
    await user.click(screen.getByRole("button", { name: /delete permanently…/i }))

    const confirmButton = screen.getByRole("button", { name: /^delete permanently$/i })
    expect(confirmButton).toBeDisabled()

    await user.type(screen.getByLabelText(/type/i), "Alice Wrong")
    expect(confirmButton).toBeDisabled()
  })

  it("arms on a case/whitespace-insensitive match and purges", async () => {
    const user = userEvent.setup()
    render(<PurgeMemberDialog member={member} />)
    await user.click(screen.getByRole("button", { name: /delete permanently…/i }))

    await user.type(screen.getByLabelText(/type/i), "  alice   SMITH ")
    const confirmButton = screen.getByRole("button", { name: /^delete permanently$/i })
    expect(confirmButton).toBeEnabled()

    await user.click(confirmButton)
    expect(mutateAsync).toHaveBeenCalledWith({ id: "m1", confirmName: "  alice   SMITH " })
    expect(mockPush).toHaveBeenCalledWith("/members")
  })

  it("spells out what is removed vs. kept", async () => {
    const user = userEvent.setup()
    render(<PurgeMemberDialog member={member} />)
    await user.click(screen.getByRole("button", { name: /delete permanently…/i }))

    expect(screen.getByText(/removed immediately/i)).toBeInTheDocument()
    expect(screen.getByText(/kept anonymized/i)).toBeInTheDocument()
    expect(screen.getByText(/cannot be undone/i)).toBeInTheDocument()
  })
})
