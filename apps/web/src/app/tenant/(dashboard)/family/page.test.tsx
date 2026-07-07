import React from "react"
import { render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import FamilyPage from "./page"
import * as familyHook from "@/hooks/use-family"
import * as advancementHook from "@/hooks/use-advancement"
import * as eventsHook from "@/hooks/use-events"
import { makeMember } from "./test-helpers"
import type { Family } from "@/types/api"

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/family",
  useSearchParams: () => new URLSearchParams(),
}))

vi.mock("@/components/page-header", () => ({
  PageHeader: ({ title }: { title: string }) => <h1>{title}</h1>,
}))

vi.mock("@/hooks/use-family", () => ({ useFamily: vi.fn() }))
vi.mock("@/hooks/use-advancement", () => ({
  useAdvancementScouts: vi.fn(),
  useMemberAdvancement: vi.fn(() => ({ data: undefined, isLoading: false })),
}))
vi.mock("@/hooks/use-events", () => ({ useEvents: vi.fn() }))

// The events strip has its own hooks/tests — stub the shared RSVP panel.
vi.mock("../events/event-rsvp-panel", () => ({
  EventRsvpPanel: () => <div data-testid="rsvp-panel" />,
}))

const useFamily = familyHook.useFamily as unknown as ReturnType<typeof vi.fn>
const useAdvancementScouts = advancementHook.useAdvancementScouts as unknown as ReturnType<
  typeof vi.fn
>
const useEvents = eventsHook.useEvents as unknown as ReturnType<typeof vi.fn>

function family(members: Family["members"]): Family {
  return { members, relationships: [] }
}

describe("FamilyPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useEvents.mockReturnValue({ data: [], isLoading: false })
    // Advancement disabled by default → no snapshot section.
    useAdvancementScouts.mockReturnValue({ data: undefined, error: new Error("404") })
  })

  it("renders a household card per family member", () => {
    const parent = makeMember({ id: "p1", first_name: "Pat", last_name: "Parent" })
    const child = makeMember({
      id: "c1",
      first_name: "Casey",
      last_name: "Parent",
      member_type: "scout",
    })
    useFamily.mockReturnValue({ data: family([parent, child]), isLoading: false })

    render(<FamilyPage />)

    const cards = screen.getAllByTestId("family-member-card")
    expect(cards).toHaveLength(2)
    expect(screen.getByText("Pat Parent")).toBeInTheDocument()
    expect(screen.getByText("Casey Parent")).toBeInTheDocument()
  })

  it("shows medical-form chips with a status", () => {
    const child = makeMember({ id: "c1", first_name: "Casey", member_type: "scout" })
    useFamily.mockReturnValue({ data: family([child]), isLoading: false })

    render(<FamilyPage />)

    // No dates on file → both parts report Missing.
    expect(screen.getByTestId("medical-chip-a/b")).toHaveAttribute("data-status", "missing")
    expect(screen.getByTestId("medical-chip-c")).toHaveAttribute("data-status", "missing")
  })

  it("degrades to self-only for a scout with no household edges", () => {
    const scout = makeMember({
      id: "s1",
      first_name: "Sam",
      last_name: "Solo",
      member_type: "scout",
    })
    useFamily.mockReturnValue({ data: family([scout]), isLoading: false })

    render(<FamilyPage />)

    expect(screen.getAllByTestId("family-member-card")).toHaveLength(1)
    expect(screen.getByText("Sam Solo")).toBeInTheDocument()
  })
})
