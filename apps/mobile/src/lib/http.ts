/**
 * Pure HTTP helpers shared by every layer (no React, no vendor imports) — so
 * the data layer (`data/commands.ts`) and the React clients (`lib/api.ts`) can
 * both use them without an import cycle.
 */

/** Pull FastAPI's `detail` out of an error body, falling back to the status. */
export function errorDetail(body: unknown, status: number): string {
  if (body && typeof body === "object" && "detail" in body) {
    return String((body as { detail: unknown }).detail)
  }
  return `HTTP ${status}`
}
