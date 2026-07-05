import { describe, expect, it, vi } from "vitest"

import { darkColors, lightColors, paletteFor } from "./theme"

// theme.ts imports `useColorScheme` from react-native; stub it so the pure
// palette logic can be exercised in Node (vitest runs with no RN runtime).
vi.mock("react-native", () => ({ useColorScheme: () => null }))

describe("theme palettes", () => {
  it("selects the dark palette only for the dark scheme", () => {
    expect(paletteFor("dark")).toBe(darkColors)
    expect(paletteFor("light")).toBe(lightColors)
    expect(paletteFor(null)).toBe(lightColors)
    expect(paletteFor(undefined)).toBe(lightColors)
  })

  it("light and dark define exactly the same tokens", () => {
    // Key parity is also enforced at compile time (darkColors: Palette); this
    // documents it and fails loudly if the type guard is ever loosened.
    expect(Object.keys(darkColors).sort()).toEqual(Object.keys(lightColors).sort())
  })

  it("every token is a non-empty string in both palettes", () => {
    for (const palette of [lightColors, darkColors]) {
      for (const value of Object.values(palette)) {
        expect(typeof value).toBe("string")
        expect(value.length).toBeGreaterThan(0)
      }
    }
  })
})
