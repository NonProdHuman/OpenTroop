import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { CalendarSubscriptionDialog } from "./calendar-subscription-dialog"
import * as subHook from "@/hooks/use-calendar-subscription"
import { toast } from "sonner"

// Mock router
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}))

// Mock calendar hook
vi.mock("@/hooks/use-calendar-subscription", () => ({
  useCalendarSubscription: vi.fn(),
}))

// Mock toast
vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

describe("CalendarSubscriptionDialog", () => {
  const mockRotate = vi.fn()
  const mockRefetch = vi.fn()
  const writeTextMock = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()

    // Set up default hook values
    vi.mocked(subHook.useCalendarSubscription).mockReturnValue({
      subscription: {
        active: true,
        token: "test-token",
        feed_path: "/calendar/test-token.ics",
      },
      isLoading: false,
      error: null,
      rotate: mockRotate,
      isRotating: false,
      refetch: mockRefetch,
    })

    // Mock clipboard
    writeTextMock.mockResolvedValue(undefined)
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText: writeTextMock },
      writable: true,
      configurable: true,
    })

    process.env.NEXT_PUBLIC_API_URL = "http://localhost:8000"
  })

  it("renders the Subscribe trigger button", () => {
    render(<CalendarSubscriptionDialog />)
    expect(screen.getByRole("button", { name: /subscribe/i })).toBeInTheDocument()
  })

  it("opens the dialog when the trigger is clicked", async () => {
    render(<CalendarSubscriptionDialog />)
    await userEvent.click(screen.getByRole("button", { name: /subscribe/i }))

    expect(screen.getByRole("heading", { name: "Subscribe to Calendar" })).toBeInTheDocument()
    expect(screen.getByText("Subscribe in Calendar App")).toBeInTheDocument()
    expect(screen.getByLabelText("Calendar Feed URL")).toHaveValue("http://localhost:8000/calendar/test-token.ics")
  })

  it("renders loading state correctly", async () => {
    vi.mocked(subHook.useCalendarSubscription).mockReturnValue({
      subscription: undefined,
      isLoading: true,
      error: null,
      rotate: mockRotate,
      isRotating: false,
      refetch: mockRefetch,
    })

    render(<CalendarSubscriptionDialog />)
    await userEvent.click(screen.getByRole("button", { name: /subscribe/i }))

    expect(screen.getByText("Loading calendar feed URL...")).toBeInTheDocument()
    expect(screen.queryByText("Subscribe in Calendar App")).not.toBeInTheDocument()
  })

  it("renders error state correctly", async () => {
    vi.mocked(subHook.useCalendarSubscription).mockReturnValue({
      subscription: undefined,
      isLoading: false,
      error: new Error("Fail"),
      rotate: mockRotate,
      isRotating: false,
      refetch: mockRefetch,
    })

    render(<CalendarSubscriptionDialog />)
    await userEvent.click(screen.getByRole("button", { name: /subscribe/i }))

    expect(screen.getByText("Failed to load calendar subscription. Please try again.")).toBeInTheDocument()
  })

  it("copies the feed link to clipboard on copy click", async () => {
    render(<CalendarSubscriptionDialog />)
    await userEvent.click(screen.getByRole("button", { name: /subscribe/i }))

    // Locate the copy icon/button (it is size icon variant outline next to the input)
    // The Input is labeled by "Calendar Feed URL", or we can get the button by its role/icon
    const copyButton = screen.getAllByRole("button").find(b => b.querySelector("svg"))
    expect(copyButton).toBeDefined()

    if (copyButton) {
      await userEvent.click(copyButton)
      expect(writeTextMock).toHaveBeenCalledWith("http://localhost:8000/calendar/test-token.ics")
      expect(toast.success).toHaveBeenCalledWith("Calendar feed URL copied")
    }
  })

  it("confirms and triggers token rotation", async () => {
    mockRotate.mockImplementation((_payload, opts) => opts?.onSuccess?.())

    render(<CalendarSubscriptionDialog />)
    await userEvent.click(screen.getByRole("button", { name: /subscribe/i }))

    // Find and click the link "Reset link"
    const resetButton = screen.getByRole("button", { name: "Reset link" })
    await userEvent.click(resetButton)

    // Verify warning is shown
    expect(screen.getByRole("heading", { name: "Are you absolutely sure?" })).toBeInTheDocument()

    // Find and click the confirm button
    const confirmButton = screen.getByRole("button", { name: "Yes, reset link" })
    await userEvent.click(confirmButton)

    expect(mockRotate).toHaveBeenCalled()
  })

  it("shows the shown-once notice when the feed is active but the URL is not available", async () => {
    vi.mocked(subHook.useCalendarSubscription).mockReturnValue({
      subscription: { active: true, token: null, feed_path: null },
      isLoading: false,
      error: null,
      rotate: mockRotate,
      isRotating: false,
      refetch: mockRefetch,
    })

    render(<CalendarSubscriptionDialog />)
    await userEvent.click(screen.getByRole("button", { name: /subscribe/i }))

    expect(screen.getByText("Your calendar feed is active")).toBeInTheDocument()
    expect(screen.queryByText("Subscribe in Calendar App")).not.toBeInTheDocument()
    // The reset affordance is still offered so the member can get a fresh URL.
    expect(screen.getByRole("button", { name: "Reset link" })).toBeInTheDocument()
  })
})
