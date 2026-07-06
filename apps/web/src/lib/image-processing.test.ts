import { describe, expect, it } from "vitest"
import { fitWithin, isSupportedImage } from "./image-processing"

describe("fitWithin", () => {
  it("leaves small images untouched", () => {
    expect(fitWithin(800, 600)).toEqual({ width: 800, height: 600 })
  })

  it("scales the long edge down to the cap, preserving aspect", () => {
    expect(fitWithin(4096, 3072)).toEqual({ width: 2048, height: 1536 })
    expect(fitWithin(3072, 4096)).toEqual({ width: 1536, height: 2048 })
  })

  it("never scales up", () => {
    expect(fitWithin(100, 50, 2048)).toEqual({ width: 100, height: 50 })
  })

  it("honors a custom edge cap", () => {
    expect(fitWithin(1000, 500, 100)).toEqual({ width: 100, height: 50 })
  })
})

describe("isSupportedImage", () => {
  it("accepts jpeg/png/webp and rejects everything else", () => {
    expect(isSupportedImage(new File([], "a.jpg", { type: "image/jpeg" }))).toBe(true)
    expect(isSupportedImage(new File([], "a.png", { type: "image/png" }))).toBe(true)
    expect(isSupportedImage(new File([], "a.webp", { type: "image/webp" }))).toBe(true)
    // HEIC can't be canvas-decoded in browsers, so it can't pass the EXIF strip.
    expect(isSupportedImage(new File([], "a.heic", { type: "image/heic" }))).toBe(false)
    expect(isSupportedImage(new File([], "a.pdf", { type: "application/pdf" }))).toBe(false)
  })
})
