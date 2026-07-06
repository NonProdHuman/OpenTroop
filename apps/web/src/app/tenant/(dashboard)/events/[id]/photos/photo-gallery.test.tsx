import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi, beforeEach } from "vitest"
import { PhotoGallery } from "./photo-gallery"
import type { EventPhoto } from "@/types/api"

const mutateMock = vi.fn()

vi.mock("@/hooks/use-event-photos", () => ({
  useDeletePhoto: () => ({ mutate: mutateMock }),
}))

vi.mock("@/lib/api", () => ({
  useApi: () => ({ request: vi.fn() }),
}))

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

function photo(overrides: Partial<EventPhoto> = {}): EventPhoto {
  return {
    id: "p1",
    tenant_id: "t1",
    created_at: "2026-07-06T00:00:00Z",
    updated_at: "2026-07-06T00:00:00Z",
    is_deleted: false,
    event_id: "e1",
    uploaded_by_member_id: "m1",
    content_type: "image/jpeg",
    byte_size: 1000,
    width: 2048,
    height: 1536,
    thumbhash: null,
    checksum_sha256: null,
    status: "ready",
    caption: null,
    taken_at: null,
    display_url: "https://storage.example/p1.jpg",
    ...overrides,
  } as EventPhoto
}

describe("PhotoGallery", () => {
  beforeEach(() => vi.clearAllMocks())

  it("shows the empty state when there are no photos", () => {
    render(
      <PhotoGallery
        eventId="e1"
        photos={[]}
        isLoading={false}
        canModerate={false}
        currentMemberId="m1"
      />,
    )
    expect(screen.getByText(/no photos yet/i)).toBeInTheDocument()
  })

  it("renders a tile per photo with its presigned URL", () => {
    render(
      <PhotoGallery
        eventId="e1"
        photos={[photo(), photo({ id: "p2", display_url: "https://storage.example/p2.jpg" })]}
        isLoading={false}
        canModerate={false}
        currentMemberId={null}
      />,
    )
    const tiles = screen.getAllByTestId("photo-tile")
    expect(tiles).toHaveLength(2)
    // alt="" gives the img role "presentation", so query by tag.
    const img = tiles[0].querySelector("img")
    expect(img).toHaveAttribute("src", "https://storage.example/p1.jpg")
  })

  it("offers delete to the photo's owner but not to other members", () => {
    render(
      <PhotoGallery
        eventId="e1"
        photos={[photo({ uploaded_by_member_id: "me" }), photo({ id: "p2" })]}
        isLoading={false}
        canModerate={false}
        currentMemberId="me"
      />,
    )
    // Only the owned photo has a delete affordance.
    expect(screen.getAllByTestId("delete-photo")).toHaveLength(1)
  })

  it("offers delete on every photo to a moderator", () => {
    render(
      <PhotoGallery
        eventId="e1"
        photos={[photo(), photo({ id: "p2" })]}
        isLoading={false}
        canModerate={true}
        currentMemberId={null}
      />,
    )
    expect(screen.getAllByTestId("delete-photo")).toHaveLength(2)
  })
})
