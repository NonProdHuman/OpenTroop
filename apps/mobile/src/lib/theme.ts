import { useColorScheme } from "react-native"

/**
 * Design tokens — the single source of truth for color, in light and dark.
 *
 * Screens read the active palette via `useColors()`, which follows the OS
 * appearance (`userInterfaceStyle: "automatic"` in app.json) and re-renders on
 * change. A future manual override (System / Light / Dark) slots behind the
 * same hook without touching a screen. See GH-210.
 *
 * Values track the Tailwind ramp the web app uses. In dark mode a saturated
 * blue cannot be both a button *fill* (needs white text on it) and an *accent*
 * on a dark surface (needs to be light), so those roles are separate tokens:
 *   - `brand` / `onBrand` — primary fill and the text/icon on it.
 *   - `accent` / `accentTint` — interactive text, borders, selected states, and
 *     the tint behind them.
 */

export const lightColors = {
  // Surfaces
  background: "#f9fafb", // gray-50 — screen background
  surface: "#ffffff", // cards, sheets, rows
  overlay: "rgba(0,0,0,0.4)", // modal scrim

  // Brand fill + its foreground
  brand: "#1d4ed8", // blue-700 — button / control fill
  onBrand: "#ffffff", // text/icon on a brand fill

  // Interactive accent (text, borders, selection)
  accent: "#1d4ed8", // blue-700
  accentTint: "#dbeafe", // blue-100 — selected pill / chip background

  // Text (gray ramp, strongest → subtlest)
  textStrong: "#111827", // gray-900 — headings
  text: "#374151", // gray-700 — body
  textSecondary: "#4b5563", // gray-600
  textMuted: "#6b7280", // gray-500 — secondary / captions
  textSubtle: "#9ca3af", // gray-400 — placeholders, empty states, disabled fills

  // Lines
  border: "#d1d5db", // gray-300 — inputs
  borderLight: "#e5e7eb", // gray-200 — cards
  hairline: "#f3f4f6", // gray-100 — row separators

  // Feedback
  danger: "#b91c1c", // red-700 — error text
  dangerStrong: "#991b1b", // red-800
  dangerBg: "#fef2f2", // red-50 — error surface
  dangerBorder: "#fecaca", // red-200
  dangerInput: "#f87171", // red-400 — invalid input outline
  warning: "#b45309", // amber-700
  success: "#059669", // emerald-600
} as const

/**
 * Same keys as `lightColors`, any string value — so `darkColors: Palette` is a
 * compile-time key-parity check (missing or extra tokens fail tsc) without
 * pinning the values to light's literals.
 */
export type Palette = Record<keyof typeof lightColors, string>

/** Dark palette. Typed as `Palette` so tsc enforces exact key parity with light. */
export const darkColors: Palette = {
  // Surfaces
  background: "#111827", // gray-900
  surface: "#1f2937", // gray-800
  overlay: "rgba(0,0,0,0.6)",

  // Brand fill + its foreground
  brand: "#2563eb", // blue-600 — darker fill keeps the white label legible
  onBrand: "#ffffff",

  // Interactive accent
  accent: "#60a5fa", // blue-400 — light enough to read on a dark surface
  accentTint: "#172554", // blue-950 — selected background behind the accent

  // Text
  textStrong: "#f9fafb", // gray-50
  text: "#e5e7eb", // gray-200
  textSecondary: "#cbd5e1", // slate-300
  textMuted: "#9ca3af", // gray-400
  textSubtle: "#6b7280", // gray-500

  // Lines
  border: "#4b5563", // gray-600 — input outline on dark
  borderLight: "#374151", // gray-700 — card edges
  hairline: "#2f3846", // subtle row separator on `surface`

  // Feedback (lifted for contrast on a dark surface)
  danger: "#f87171", // red-400
  dangerStrong: "#fca5a5", // red-300
  dangerBg: "#450a0a", // red-950 — error surface
  dangerBorder: "#7f1d1d", // red-900
  dangerInput: "#f87171", // red-400
  warning: "#fbbf24", // amber-400
  success: "#34d399", // emerald-400
}

/** Pure palette selector — testable without React Native. */
export function paletteFor(scheme: string | null | undefined): Palette {
  return scheme === "dark" ? darkColors : lightColors
}

/** The active palette, following the OS appearance and re-rendering on change. */
export function useColors(): Palette {
  return paletteFor(useColorScheme())
}
