/**
 * Design tokens — the single source of truth for color.
 *
 * Values track the Tailwind ramp the web app uses, so the two clients stay
 * visually consistent. Screens reference `colors.*` rather than inline hex, so
 * a rebrand or a future dark-mode pass is one edit here instead of a
 * find-and-replace across every screen. (Plain `"white"` stays literal — it is
 * not a brand color and would not move in a rebrand.)
 */

export const colors = {
  // Brand
  brand: "#1d4ed8", // blue-700 — primary actions, selection, links
  brandTint: "#dbeafe", // blue-100 — selected pill / chip background

  overlay: "rgba(0,0,0,0.4)", // modal scrim

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
