export function formatDate(value: string | null | undefined): string | null {
  if (!value) return null
  try {
    return new Date(value + "T00:00:00").toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    })
  } catch {
    return value
  }
}
