import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { MemberAdvancementView } from "./member-advancement-view"
import * as advancementHooks from "@/hooks/use-advancement"
import * as sessionHooks from "@/hooks/use-session"
import type { MemberAdvancement } from "@/types/api"

vi.mock("@/hooks/use-advancement", () => ({
  useMemberAdvancement: vi.fn(),
  useMeritBadges: vi.fn(() => ({ data: [] })),
  useCreateCompletion: vi.fn(),
  useUpdateCompletion: vi.fn(() => ({ mutate: vi.fn() })),
  useRevokeCompletion: vi.fn(() => ({ mutate: vi.fn() })),
  useUpdateRankProgress: vi.fn(() => ({ mutate: vi.fn() })),
  useCreateMemberMeritBadge: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
}))

vi.mock("@/hooks/use-session", () => ({
  usePermissions: vi.fn(),
  useSession: vi.fn(() => ({ data: { member: { id: "m1" } } })),
}))

vi.mock("@/hooks/use-tenant-settings", () => ({
  useTenantSettings: vi.fn(() => ({ data: { advancement_mode: "chair_entry" } })),
}))

const createMutate = vi.fn()

function mockPermissions(perms: string[]) {
  vi.mocked(sessionHooks.usePermissions).mockReturnValue({
    has: (p: string) => perms.includes(p),
    isMember: true,
    isLoading: false,
  } as unknown as ReturnType<typeof sessionHooks.usePermissions>)
}

function advancement(overrides: {
  completed_date?: string | null
  awarded_date?: string | null
  completion?: object | null
}): MemberAdvancement {
  return {
    ranks: [
      {
        rank: { id: "r1", name: "Tenderfoot", code: "tenderfoot" },
        requirement_set: { id: "s1", version: "2025" },
        progress: {
          id: "p1",
          completed_date: overrides.completed_date ?? null,
          awarded_date: overrides.awarded_date ?? null,
        },
        is_complete: false,
        requirements: [
          {
            requirement: { id: "q1", label: "1a", letter: "a", text: "Pitch a tent." },
            completion: overrides.completion ?? null,
            is_complete: overrides.completion != null,
            metrics_progress: [],
          },
        ],
      },
    ],
    merit_badges: [],
  } as unknown as MemberAdvancement
}

function renderView(data: MemberAdvancement) {
  vi.mocked(advancementHooks.useMemberAdvancement).mockReturnValue({
    data,
    isLoading: false,
    error: null,
  } as unknown as ReturnType<typeof advancementHooks.useMemberAdvancement>)
  vi.mocked(advancementHooks.useCreateCompletion).mockReturnValue({
    mutate: createMutate,
    isPending: false,
  } as unknown as ReturnType<typeof advancementHooks.useCreateCompletion>)
  render(<MemberAdvancementView memberId="m1" />)
}

describe("MemberAdvancementView (#256)", () => {
  beforeEach(() => vi.clearAllMocks())

  it("locks an awarded rank: no action buttons, dates shown read-only", () => {
    mockPermissions(["advancement:read", "advancement:record", "advancement:approve"])
    renderView(
      advancement({
        completed_date: "2026-06-01",
        awarded_date: "2026-06-20",
        completion: {
          id: "c1",
          status: "approved",
          date_completed: "2026-05-01",
          recorded_via: "manual",
          note: null,
        },
      }),
    )
    expect(screen.getByTestId("earned-badge")).toHaveTextContent("Earned 2026-06-01")
    expect(screen.getByTestId("awarded-badge")).toHaveTextContent("Awarded 2026-06-20")
    expect(screen.queryByRole("button", { name: /mark complete/i })).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /revoke/i })).not.toBeInTheDocument()
    // Completion date is plain text, not an editable input, once awarded.
    expect(screen.getByText("2026-05-01")).toBeInTheDocument()
    expect(screen.queryByLabelText(/edit completion date/i)).not.toBeInTheDocument()
  })

  it("records with an editable date defaulting to today", async () => {
    mockPermissions(["advancement:read", "advancement:record"])
    renderView(advancement({ completion: null }))
    const todayIso = new Date().toISOString().slice(0, 10)
    const dateInput = screen.getByLabelText(/completion date for 1a/i)
    expect(dateInput).toHaveValue(todayIso)

    await userEvent.clear(dateInput)
    await userEvent.type(dateInput, "2026-05-04")
    await userEvent.click(screen.getByRole("button", { name: /mark complete/i }))
    expect(createMutate).toHaveBeenCalledWith({
      requirement_id: "q1",
      date_completed: "2026-05-04",
    })
  })

  it("closes self-report once the rank is earned", async () => {
    const { useTenantSettings } = await import("@/hooks/use-tenant-settings")
    vi.mocked(useTenantSettings).mockReturnValue({
      data: { advancement_mode: "scout_reported" },
    } as unknown as ReturnType<typeof useTenantSettings>)
    mockPermissions([]) // the scout themselves — no staff permissions
    renderView(advancement({ completed_date: "2026-06-01", completion: null }))
    // The requirement row's report affordance (date input + button) must be gone;
    // the merit-badge section keeps its own Report control, so scope to the row.
    expect(screen.queryByLabelText(/completion date for 1a/i)).not.toBeInTheDocument()
  })
})
