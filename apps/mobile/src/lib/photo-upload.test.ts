import { describe, expect, it, vi } from "vitest"
import { uploadPhotos, type PipelineDeps, type UploadProgress } from "./photo-upload"

function makeDeps(overrides: Partial<PipelineDeps> = {}): PipelineDeps {
  return {
    api: vi.fn(async (path: string) => {
      if (path.endsWith("/photos/initiate")) {
        return {
          uploads: [
            { photo_id: "p1", upload_url: "https://bucket/put/p1", expires_in_seconds: 600 },
          ],
        }
      }
      return {}
    }) as PipelineDeps["api"],
    manipulate: vi.fn(async (uri: string) => ({
      uri: `${uri}-processed.jpg`,
      width: 2048,
      height: 1536,
      byteLength: 400_000,
    })),
    putFile: vi.fn(async () => 200),
    ...overrides,
  }
}

const asset = (n: number) => ({ uri: `file:///pick/${n}.heic`, fileName: `IMG_${n}.heic` })

describe("uploadPhotos", () => {
  it("drives manipulate → initiate → PUT → complete for each asset", async () => {
    const deps = makeDeps()
    const result = await uploadPhotos(deps, "e1", [asset(1), asset(2)])

    expect(result).toEqual({ uploaded: 2, failed: 0 })
    expect(deps.manipulate).toHaveBeenCalledTimes(2)
    // initiate + complete per asset
    expect(deps.api).toHaveBeenCalledTimes(4)
    expect(deps.api).toHaveBeenCalledWith("/events/e1/photos/initiate", {
      method: "POST",
      body: {
        photos: [
          { content_type: "image/jpeg", byte_length: 400_000, width: 2048, height: 1536 },
        ],
      },
    })
    expect(deps.api).toHaveBeenCalledWith("/photos/p1/complete", { method: "POST" })
    // The PUT uploads the PROCESSED (downscaled, EXIF-stripped) file, never the original.
    expect(deps.putFile).toHaveBeenCalledWith(
      "https://bucket/put/p1",
      "file:///pick/1.heic-processed.jpg",
      "image/jpeg",
    )
  })

  it("isolates a failing file and continues with the rest", async () => {
    const deps = makeDeps({
      putFile: vi
        .fn()
        .mockResolvedValueOnce(500) // first file's storage PUT fails
        .mockResolvedValue(200),
    })
    const events: UploadProgress[] = []
    const result = await uploadPhotos(deps, "e1", [asset(1), asset(2)], (p) => events.push(p))

    expect(result).toEqual({ uploaded: 1, failed: 1 })
    const first = events.filter((e) => e.index === 0).map((e) => e.status)
    const second = events.filter((e) => e.index === 1).map((e) => e.status)
    expect(first).toEqual(["processing", "uploading", "error"])
    expect(second).toEqual(["processing", "uploading", "done"])
  })

  it("never calls complete when the storage PUT failed", async () => {
    const deps = makeDeps({ putFile: vi.fn(async () => 403) })
    await uploadPhotos(deps, "e1", [asset(1)])
    const calls = vi.mocked(deps.api).mock.calls.map(([path]) => path)
    expect(calls).toEqual(["/events/e1/photos/initiate"])
  })

  it("surfaces a quota rejection (413) as that file's error", async () => {
    const deps = makeDeps({
      api: vi.fn(async (path: string) => {
        if (path.endsWith("/photos/initiate")) throw new Error("Troop storage quota exceeded")
        return {}
      }) as PipelineDeps["api"],
    })
    const events: UploadProgress[] = []
    const result = await uploadPhotos(deps, "e1", [asset(1)], (p) => events.push(p))
    expect(result).toEqual({ uploaded: 0, failed: 1 })
    expect(events.at(-1)).toMatchObject({
      status: "error",
      error: "Troop storage quota exceeded",
    })
    expect(deps.putFile).not.toHaveBeenCalled()
  })
})
