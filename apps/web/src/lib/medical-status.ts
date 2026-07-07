/**
 * BSA medical-form expiry status — mirrors the backend Medical-form report
 * (`app/core/reports.py`): each part (A/B and C) is valid for one year from its
 * date, and "expiring soon" is the report's default 90-day horizon.
 *
 * Keep these constants in sync with `_MEDICAL_VALID_DAYS` and the medical
 * report's `horizon_days` default so the family page and the leader report agree.
 */

export const MEDICAL_VALID_DAYS = 365
export const MEDICAL_HORIZON_DAYS = 90

export type MedicalStatus = "missing" | "expired" | "expiring" | "valid"

/** Days until a form (dated `formDate`) expires; null if no date recorded. */
export function medicalDaysUntil(formDate: string | null | undefined): number | null {
  if (!formDate) return null
  const expiry = new Date(formDate)
  expiry.setDate(expiry.getDate() + MEDICAL_VALID_DAYS)
  const today = new Date()
  const ms = expiry.getTime() - today.getTime()
  return Math.ceil(ms / (1000 * 60 * 60 * 24))
}

export function medicalStatus(formDate: string | null | undefined): MedicalStatus {
  const days = medicalDaysUntil(formDate)
  if (days === null) return "missing"
  if (days <= 0) return "expired"
  if (days <= MEDICAL_HORIZON_DAYS) return "expiring"
  return "valid"
}

/** Tailwind chip classes per status (green/amber/red, matching the report tone). */
export const MEDICAL_STATUS_CLASSES: Record<MedicalStatus, string> = {
  valid: "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300",
  expiring: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  expired: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
  missing: "bg-muted text-muted-foreground",
}

export function medicalStatusLabel(status: MedicalStatus): string {
  switch (status) {
    case "valid":
      return "Current"
    case "expiring":
      return "Expiring soon"
    case "expired":
      return "Expired"
    case "missing":
      return "Missing"
  }
}
