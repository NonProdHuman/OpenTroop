import { fireEvent, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import NewEventPage from "./page"

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

vi.mock("@/hooks/use-locations", () => ({
  useLocations: () => ({ data: [] }),
}))

vi.mock("@/hooks/use-events", () => ({
  useCreateEvent: () => ({ mutate, isPending: false }),
  useEventTypes: () => ({
    data: [{ id: "type-1", name: "Campout", is_active: true }],
  }),
}))

describe("NewEventPage", () => {
  beforeEach(() => {
    push.mockReset()
    mutate.mockReset()
  })

  it("requires a name before submitting", async () => {
    render(<NewEventPage />)
    await userEvent.click(screen.getAllByRole("button", { name: /create event/i })[0])
    expect(screen.getByText("Event name is required.")).toBeInTheDocument()
    expect(mutate).not.toHaveBeenCalled()
  })

  it("blocks submit when the end is before the start", async () => {
    const { container } = render(<NewEventPage />)
    await userEvent.type(screen.getAllByRole("textbox")[0], "Fall Campout")

    const dt = container.querySelectorAll<HTMLInputElement>('input[type="datetime-local"]')
    // dt[0] = start, dt[1] = end. Move end into the past.
    fireEvent.change(dt[1], { target: { value: "2020-01-01T00:00" } })

    await userEvent.click(screen.getAllByRole("button", { name: /create event/i })[0])
    expect(screen.getByText("End time cannot be before the start time.")).toBeInTheDocument()
    expect(mutate).not.toHaveBeenCalled()
  })

  it("submits a valid event with the resolved event type and navigates", async () => {
    mutate.mockImplementation((_payload, opts) => opts?.onSuccess?.())
    render(<NewEventPage />)

    await userEvent.type(screen.getAllByRole("textbox")[0], "Fall Campout")
    await userEvent.click(screen.getAllByRole("button", { name: /create event/i })[0])

    expect(mutate).toHaveBeenCalledTimes(1)
    const payload = mutate.mock.calls[0][0]
    expect(payload).toMatchObject({
      name: "Fall Campout",
      event_type_id: "type-1",
      all_day: false,
    })
    // Times are sent to the backend as UTC ISO instants.
    expect(payload.scheduled_start).toMatch(/Z$/)
    expect(payload.scheduled_end).toMatch(/Z$/)
    expect(push).toHaveBeenCalledWith("/events")
  })
})
