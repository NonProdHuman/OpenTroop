"use client"

import { useTenants } from "@/hooks/use-platform"
import { ConsoleHeader } from "../_components/console-header"
import { TenantsTable } from "../_components/tenants-table"
import { CreateTenantDialog } from "./create-tenant-dialog"

export default function TenantsPage() {
  const { data: tenants = [], isLoading, isError, error } = useTenants()

  return (
    <>
      <ConsoleHeader title={`Tenants${tenants.length ? ` (${tenants.length})` : ""}`}>
        <CreateTenantDialog />
      </ConsoleHeader>

      <div className="flex-1 space-y-4 p-4 md:p-6">
        {isError ? (
          <p className="text-sm text-destructive">
            Couldn’t load tenants: {error instanceof Error ? error.message : "unknown error"}
          </p>
        ) : (
          <div className="rounded-md border">
            <TenantsTable tenants={tenants} isLoading={isLoading} />
          </div>
        )}
      </div>
    </>
  )
}
