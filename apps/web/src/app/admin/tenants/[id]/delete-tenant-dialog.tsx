"use client"

import { TriangleAlert } from "lucide-react"
import { useRouter } from "next/navigation"
import { useState } from "react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useDeleteTenant } from "@/hooks/use-platform"
import { apiErrorMessage } from "@/lib/api"
import type { Tenant } from "@/types/api"

/** Whether the tenant delete gates are satisfied client-side: suspended, with a
 * data export taken after the suspension. The backend re-enforces both. */
export function deleteGatesSatisfied(tenant: Tenant): boolean {
  if (!tenant.suspended_at) return false
  if (!tenant.last_export_at) return false
  return new Date(tenant.last_export_at) >= new Date(tenant.suspended_at)
}

/** Type-the-slug confirmation for the immediate, irreversible tenant purge
 * (GH-222). The downloaded export is the only recovery path. */
export function DeleteTenantDialog({ tenant }: { tenant: Tenant }) {
  const router = useRouter()
  const deleteTenant = useDeleteTenant(tenant.id)
  const [open, setOpen] = useState(false)
  const [confirm, setConfirm] = useState("")

  const ready = deleteGatesSatisfied(tenant)
  const armed = confirm === tenant.slug

  function handleOpenChange(next: boolean) {
    setOpen(next)
    if (!next) setConfirm("")
  }

  async function handleDelete() {
    try {
      await deleteTenant.mutateAsync(confirm)
      toast.success(`Tenant "${tenant.slug}" permanently deleted`)
      router.push("/tenants")
    } catch (err) {
      toast.error(
        apiErrorMessage(err, {
          400: "The slug you typed doesn't match.",
          403: "Only a superadmin can delete a tenant.",
          409: "Delete is blocked: the tenant must be suspended and exported (after suspension) first.",
        }),
      )
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger
        render={
          <Button variant="destructive" size="sm" disabled={!ready}>
            <TriangleAlert className="h-4 w-4" />
            Delete tenant…
          </Button>
        }
      />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Permanently delete {tenant.name}?</DialogTitle>
          <DialogDescription>
            Immediate and irreversible: every member, event, message, and record this troop owns
            is erased, and the subdomain <span className="font-mono">{tenant.slug}</span> is freed
            for reuse. The downloaded export file is the only way back.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-2">
          <Label htmlFor="delete-tenant-confirm">
            Type <span className="font-mono font-semibold">{tenant.slug}</span> to confirm
          </Label>
          <Input
            id="delete-tenant-confirm"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            placeholder={tenant.slug}
            autoComplete="off"
          />
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => handleOpenChange(false)}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={handleDelete}
            disabled={!armed || deleteTenant.isPending}
          >
            {deleteTenant.isPending ? "Deleting…" : "Delete tenant"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
