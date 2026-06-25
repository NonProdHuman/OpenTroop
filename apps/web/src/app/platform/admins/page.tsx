"use client"

import { toast } from "sonner"
import { useMe } from "@/hooks/use-me"
import { usePlatformAdmins, useRevokePlatformAdmin } from "@/hooks/use-platform"
import type { PlatformAdmin } from "@/types/api"
import { AdminsTable } from "../_components/admins-table"
import { ConsoleHeader } from "../_components/console-header"
import { GrantAdminDialog } from "./grant-admin-dialog"

export default function PlatformAdminsPage() {
  const { data: me } = useMe()
  const isSuperadmin = me?.platform_role === "superadmin"
  const { data: admins = [], isLoading, isError, error } = usePlatformAdmins()
  const revoke = useRevokePlatformAdmin()

  async function handleRevoke(admin: PlatformAdmin) {
    const who = admin.email ?? admin.display_name ?? "this user"
    if (!window.confirm(`Revoke platform access for ${who}?`)) return
    try {
      await revoke.mutateAsync(admin.user_id)
      toast.success("Platform access revoked")
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to revoke")
    }
  }

  return (
    <>
      <ConsoleHeader title="Platform admins">{isSuperadmin ? <GrantAdminDialog /> : null}</ConsoleHeader>

      <div className="flex-1 space-y-4 p-4 md:p-6">
        {!isSuperadmin ? (
          <p className="text-sm text-muted-foreground">
            You can view platform administrators. Granting and revoking roles is limited to
            superadmins.
          </p>
        ) : null}
        {isError ? (
          <p className="text-sm text-destructive">
            Couldn’t load admins: {error instanceof Error ? error.message : "unknown error"}
          </p>
        ) : (
          <div className="rounded-md border">
            <AdminsTable
              admins={admins}
              isLoading={isLoading}
              canManage={isSuperadmin}
              onRevoke={handleRevoke}
            />
          </div>
        )}
      </div>
    </>
  )
}
