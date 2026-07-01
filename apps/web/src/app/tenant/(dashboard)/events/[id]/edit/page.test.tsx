import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import EventEditPage from "./page"
import type { Event } from "@/types/api"

const push = vi.fn()
const updateMutate = vi.fn()

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
  useParams: () => ({ id: "event-1" }),
}))

vi.mock("@/components/page-header", () => ({
  PageHeader: ({ title, children }: { title: string; children?: React.ReactNode }) => (
    <div>
      <h1>{title}</h1>
      {children}
    </div>
  ),
}))

// Keep the RSVP tab content out of this Details-focused test.
vi.mock("./event-rsvp-admin", () => ({
  EventRsvpAdmin: () => <div>rsvp-admin</div>,
}))

const event: Partial<Event> = {
  id: "event-1",
  name: "Fall Campout",
  event_type_id: "type-1",
  location_id: null,
  scheduled_start: "2026-09-01T18:00:00.000Z",
  scheduled_end: "2026-09-01T19:00:00.000Z",
  all_day: false,
}

vi.mock("@/hooks/use-events", () => ({
  useEvent: () => ({ data: event, isLoading: false }),
  useUpdateEvent: () => ({ mutate: updateMutate, isPending: false }),
  useEventTypes: () => ({ data: [{ id: "type-1", name: "Campout", is_active: true }] }),
  useLocations: () => ({ data: [] }),
  useEventAudiences: () => ({ data: [] }),
  useAddEventAudience: () => ({ mutate: vi.fn() }),
  useRemoveEventAudience: () => ({ mutate: vi.fn() }),
  useEventOrganizers: () => ({ data: [] }),
  useAddEventOrganizer: () => ({ mutate: vi.fn() }),
  useRemoveEventOrganizer: () => ({ mutate: vi.fn() }),
}))

vi.mock("@/hooks/use-groups", () => ({
  useGroups: () => ({ data: [] }),
}))

vi.mock("@/hooks/use-members", () => ({
  useMembers: () => ({ data: [] }),
}))

describe("EventEditPage", () => {
  beforeEach(() => {
    push.mockReset()
    updateMutate.mockReset()
  })

  it("seeds the form from the event and PATCHes edited fields on save", async () => {
    updateMutate.mockImplementation((_args, opts) => opts?.onSuccess?.())
    render(<EventEditPage />)

    const nameInput = screen.getAllByRole("textbox")[0] as HTMLInputElement
    expect(nameInput.value).toBe("Fall Campout")

    await userEvent.clear(nameInput)
    await userEvent.type(nameInput, "Spring Campout")
    await userEvent.click(screen.getAllByRole("button", { name: /save/i })[0])

    expect(updateMutate).toHaveBeenCalledTimes(1)
    const [arg] = updateMutate.mock.calls[0]
    expect(arg.id).toBe("event-1")
    expect(arg.data).toMatchObject({
      name: "Spring Campout",
      event_type_id: "type-1",
      all_day: false,
    })
    expect(arg.data.scheduled_start).toMatch(/Z$/)
    expect(push).toHaveBeenCalledWith("/events")
  })

  it("blocks save when the name is cleared", async () => {
    render(<EventEditPage />)
    const nameInput = screen.getAllByRole("textbox")[0] as HTMLInputElement
    await userEvent.clear(nameInput)
    await userEvent.click(screen.getAllByRole("button", { name: /save/i })[0])

    expect(screen.getByText("Event name is required.")).toBeInTheDocument()
    expect(updateMutate).not.toHaveBeenCalled()
  })
})
