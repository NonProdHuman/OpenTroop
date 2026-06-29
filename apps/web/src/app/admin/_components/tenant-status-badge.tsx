import type { Tenant } from "@/types/api"

/** Active vs. Suspended pill for a tenant — soft tinted pattern. */
export function TenantStatusBadge({ tenant }: { tenant: Pick<Tenant, "suspended_at"> }) {
  if (tenant.suspended_at) {
    return (
      <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-red-50 text-red-700 border border-red-200 dark:bg-red-950 dark:text-red-300 dark:border-red-900">
        Suspended
      </span>
    )
  }
  return (
    <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-green-50 text-green-700 border border-green-200 dark:bg-green-950 dark:text-green-300 dark:border-green-900">
      Active
    </span>
  )
}
