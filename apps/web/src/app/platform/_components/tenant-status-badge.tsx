import { Badge } from "@/components/ui/badge"
import type { Tenant } from "@/types/api"

/** Active vs. Suspended pill for a tenant. */
export function TenantStatusBadge({ tenant }: { tenant: Pick<Tenant, "suspended_at"> }) {
  if (tenant.suspended_at) {
    return <Badge variant="destructive">Suspended</Badge>
  }
  return <Badge variant="secondary">Active</Badge>
}
