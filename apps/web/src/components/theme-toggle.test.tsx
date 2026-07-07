import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi, beforeEach } from "vitest"
import { ThemeToggle } from "./theme-toggle"
import * as nextThemes from "next-themes"

vi.mock("next-themes", () => ({
  useTheme: vi.fn(),
}))

const setTheme = vi.fn()

function mockTheme(theme: string | undefined) {
  vi.mocked(nextThemes.useTheme).mockReturnValue({
    theme,
    setTheme,
  } as unknown as ReturnType<typeof nextThemes.useTheme>)
}

describe("ThemeToggle", () => {
  beforeEach(() => vi.clearAllMocks())

  it("offers light, system, and dark — system must stay reachable", () => {
    // Regression: a binary light/dark switch permanently pinned the browser to
    // an explicit theme on first click, silently ending OS light/dark syncing.
    mockTheme("system")
    render(<ThemeToggle />)
    expect(screen.getByRole("radio", { name: /light theme/i })).toBeInTheDocument()
    expect(screen.getByRole("radio", { name: /match system theme/i })).toBeInTheDocument()
    expect(screen.getByRole("radio", { name: /dark theme/i })).toBeInTheDocument()
  })

  it("marks the active theme and switches on click", async () => {
    mockTheme("dark")
    render(<ThemeToggle />)
    expect(screen.getByRole("radio", { name: /dark theme/i })).toHaveAttribute(
      "aria-checked",
      "true",
    )
    await userEvent.click(screen.getByRole("radio", { name: /match system theme/i }))
    expect(setTheme).toHaveBeenCalledWith("system")
  })

  it("defaults the highlight to system when no theme is persisted", () => {
    mockTheme(undefined)
    render(<ThemeToggle />)
    expect(screen.getByRole("radio", { name: /match system theme/i })).toHaveAttribute(
      "aria-checked",
      "true",
    )
  })
})
