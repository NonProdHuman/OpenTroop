"use client"

import { ArrowLeft, Download, Loader2, Pause, Play } from "lucide-react"
import Link from "next/link"
import { useParams } from "next/navigation"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import type { Tenant } from "@/types/api"
import {
  useExportTenant,
  useRevokeTenantAdmin,
  useSetTenantSuspended,
  useTenant,
  useTenantAdmins,
} from "@/hooks/use-platform"
import { ConsoleHeader } from "../../_components/console-header"
import { TenantStatusBadge } from "../../_components/tenant-status-badge"
import { DeleteTenantDialog, deleteGatesSatisfied } from "./delete-tenant-dialog"
import { InviteAdminDialog } from "./invite-admin-dialog"

export default function TenantDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { data: tenant, isLoading, isError } = useTenant(id)
  const setSuspended = useSetTenantSuspended(id)

  async function toggleSuspend() {
    if (!tenant) return
    const suspend = tenant.suspended_at === null
    try {
      await setSuspended.mutateAsync(suspend)
      toast.success(suspend ? "Tenant suspended" : "Suspension lifted")
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to update tenant")
    }
  }

  return (
    <>
      <ConsoleHeader title={tenant ? tenant.name : "Tenant"}>
        <Button variant="ghost" size="sm" render={<Link href="/tenants" />} nativeButton={false}>
          <ArrowLeft className="h-4 w-4" />
          All tenants
        </Button>
      </ConsoleHeader>

      <div className="flex-1 space-y-6 p-4 md:p-6">
        {isError ? (
          <p className="text-sm text-destructive">Tenant not found.</p>
        ) : isLoading || !tenant ? (
          <Skeleton className="h-24 w-full max-w-md" />
        ) : (
          <>
            <section className="flex flex-wrap items-center gap-x-6 gap-y-2">
              <div className="flex items-center gap-2">
                <span className="font-mono text-sm text-muted-foreground">{tenant.slug}</span>
                <TenantStatusBadge tenant={tenant} />
              </div>
              <Button
                size="sm"
                variant={tenant.suspended_at ? "default" : "destructive"}
                onClick={toggleSuspend}
                disabled={setSuspended.isPending}
              >
                {setSuspended.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : tenant.suspended_at ? (
                  <Play className="h-4 w-4" />
                ) : (
                  <Pause className="h-4 w-4" />
                )}
                {tenant.suspended_at ? "Unsuspend" : "Suspend"}
              </Button>
            </section>

            <AdminsSection tenantId={id} />

            <DangerZoneSection tenant={tenant} />
          </>
        )}
      </div>
    </>
  )
}

function DangerZoneSection({ tenant }: { tenant: Tenant }) {
  const exportTenant = useExportTenant(tenant.id)

  async function handleExport() {
    try {
      const bundle = await exportTenant.mutateAsync()
      const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: "application/json" })
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = `${tenant.slug}-export-${new Date().toISOString().slice(0, 10)}.json`
      a.click()
      URL.revokeObjectURL(url)
      toast.success("Export downloaded")
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Export failed")
    }
  }

  const ready = deleteGatesSatisfied(tenant)

  return (
    <section className="space-y-3">
      <h2 className="text-base font-semibold tracking-tight">Danger zone</h2>
      <div className="space-y-4 rounded-lg border border-destructive/30 p-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-sm font-medium">Export all data</p>
            <p className="text-sm text-muted-foreground">
              Full JSON bundle of every record this troop owns. Deleting the tenant requires an
              export taken after suspension — the file is also the only recovery path.
            </p>
          </div>
          <Button
            size="sm"
            variant="outline"
            onClick={handleExport}
            disabled={exportTenant.isPending}
          >
            {exportTenant.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Download className="h-4 w-4" />
            )}
            Export
          </Button>
        </div>
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-sm font-medium">Delete tenant</p>
            <p className="text-sm text-muted-foreground">
              {ready
                ? "All gates passed — deletion is armed and immediate."
                : "Locked: suspend the tenant, then take a fresh export to unlock deletion."}
            </p>
          </div>
          <DeleteTenantDialog tenant={tenant} />
        </div>
      </div>
    </section>
  )
}

function AdminsSection({ tenantId }: { tenantId: string }) {
  const { data: admins = [], isLoading } = useTenantAdmins(tenantId)
  const revoke = useRevokeTenantAdmin(tenantId)

  async function handleRevoke(memberId: string, name: string) {
    if (!window.confirm(`Revoke admin access for ${name}?`)) return
    try {
      await revoke.mutateAsync(memberId)
      toast.success("Admin access revoked")
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to revoke")
    }
  }

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold tracking-tight">Administrators</h2>
        <InviteAdminDialog tenantId={tenantId} />
      </div>

      <div className="rounded-lg border shadow-sm overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead><span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Name</span></TableHead>
              <TableHead><span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Email</span></TableHead>
              <TableHead><span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Status</span></TableHead>
              <TableHead className="w-0" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={4}>
                  <Skeleton className="h-5 w-full" />
                </TableCell>
              </TableRow>
            ) : admins.length === 0 ? (
              <TableRow>
                <TableCell colSpan={4} className="py-8 text-center text-sm text-muted-foreground">
                  No administrators.
                </TableCell>
              </TableRow>
            ) : (
              admins.map((a) => (
                <TableRow key={a.member_id} className="hover:bg-muted/40 transition-colors duration-75">
                  <TableCell className="font-medium">
                    {a.first_name} {a.last_name}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">{a.email ?? "—"}</TableCell>
                  <TableCell>
                    {a.claimed ? (
                      <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-green-50 text-green-700 border border-green-200 dark:bg-green-950 dark:text-green-300">
                        Claimed
                      </span>
                    ) : (
                      <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200 dark:bg-amber-950 dark:text-amber-300">
                        Invited
                      </span>
                    )}
                  </TableCell>
                  <TableCell>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="text-destructive hover:text-destructive"
                      onClick={() => handleRevoke(a.member_id, `${a.first_name} ${a.last_name}`)}
                      disabled={revoke.isPending}
                    >
                      Revoke
                    </Button>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
      <p className="text-xs text-muted-foreground">
        A tenant must keep at least one administrator — revoking the last one is blocked.
      </p>
    </section>
  )
}
