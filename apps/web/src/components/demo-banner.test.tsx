import { render, screen, waitFor } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

// DemoBanner reads NEXT_PUBLIC_DEMO_HOST at module load (via lib/domains), so each
// case resets modules and re-imports after stubbing the env. jsdom serves from
// http://localhost:3000/, so window.location.host is "localhost:3000".
describe("DemoBanner (GH-246)", () => {
  afterEach(() => {
    vi.unstubAllEnvs()
    vi.resetModules()
  })

  it("renders the read-only notice on the configured demo host", async () => {
    vi.resetModules()
    vi.stubEnv("NEXT_PUBLIC_DEMO_HOST", "localhost:3000")
    const { DemoBanner } = await import("./demo-banner")
    render(<DemoBanner />)

    const banner = await screen.findByTestId("demo-banner")
    expect(banner).toHaveTextContent(/read-only demo troop/i)
    expect(screen.getByRole("link", { name: /request edit access/i })).toHaveAttribute(
      "href",
      expect.stringContaining("mailto:"),
    )
  })

  it("renders nothing when the demo feature is off", async () => {
    vi.resetModules()
    const { DemoBanner } = await import("./demo-banner")
    const { container } = render(<DemoBanner />)
    // Stays empty across the mount effect.
    await waitFor(() => expect(container).toBeEmptyDOMElement())
  })

  it("renders nothing when the current host is not the demo host", async () => {
    vi.resetModules()
    vi.stubEnv("NEXT_PUBLIC_DEMO_HOST", "demo.opentroop.dev")
    const { DemoBanner } = await import("./demo-banner")
    const { container } = render(<DemoBanner />)
    await waitFor(() => expect(container).toBeEmptyDOMElement())
  })
})
