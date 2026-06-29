import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { EventTypeBadge } from "./event-type-badge"

describe("EventTypeBadge", () => {
  it("renders the type name", () => {
    render(<EventTypeBadge type={{ name: "Campout", color: "#2ECC71" }} />)
    expect(screen.getByText("Campout")).toBeInTheDocument()
  })

  it("uses the type color for the dot", () => {
    const { container } = render(<EventTypeBadge type={{ name: "Hike", color: "#F39C12" }} />)
    const dot = container.querySelector("span[aria-hidden]") as HTMLElement
    expect(dot).toBeTruthy()
    expect(dot.style.backgroundColor).toBe("rgb(243, 156, 18)")
  })

  it("falls back to a neutral color when none is set", () => {
    const { container } = render(<EventTypeBadge type={{ name: "Meeting", color: null }} />)
    const dot = container.querySelector("span[aria-hidden]") as HTMLElement
    expect(dot.style.backgroundColor).toBe("rgb(107, 114, 128)")
  })
})
