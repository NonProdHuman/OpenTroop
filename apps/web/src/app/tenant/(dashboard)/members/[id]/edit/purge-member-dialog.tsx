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
import { usePurgeMember } from "@/hooks/use-members"
import { apiErrorMessage } from "@/lib/api"
import type { Member } from "@/types/api"

const normalize = (s: string) => s.trim().replace(/\s+/g, " ").toLowerCase()

/** Danger-zone dialog for the irreversible member hard delete (GH-222).
 *
 * The backend enforces everything (admin-only, name confirmation, last-admin /
 * self / already-purged guards); this dialog's type-to-confirm mirrors the
 * server rule so the button only arms when the request would pass it. */
export function PurgeMemberDialog({ member }: { member: Member }) {
  const router = useRouter()
  const purge = usePurgeMember()
  const [open, setOpen] = useState(false)
  const [confirm, setConfirm] = useState("")

  const fullName = `${member.first_name} ${member.last_name}`
  const armed = normalize(confirm) === normalize(fullName)

  function handleOpenChange(next: boolean) {
    setOpen(next)
    if (!next) setConfirm("")
  }

  async function handlePurge() {
    try {
      await purge.mutateAsync({ id: member.id, confirmName: confirm })
      toast.success("Member permanently deleted")
      router.push("/members")
    } catch (err) {
      toast.error(
        apiErrorMessage(err, {
          400: "The name you typed doesn't match this member's full name.",
          403: "Only a tenant administrator can permanently delete a member.",
          409: "This member can't be deleted: they may be the troop's last administrator, your own record, or already deleted.",
        }),
      )
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger
        render={
          <Button variant="destructive" size="sm">
            <TriangleAlert className="h-4 w-4" />
            Delete permanently…
          </Button>
        }
      />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Permanently delete {fullName}?</DialogTitle>
          <DialogDescription>
            This cannot be undone. It is a legal-erasure action, not a roster removal — use
            &ldquo;status: inactive/alumni&rdquo; or the ordinary remove for those.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3 text-sm">
          <div>
            <p className="font-medium">Removed immediately:</p>
            <ul className="mt-1 list-disc pl-5 text-muted-foreground">
              <li>Name, birth date, contact and address details</li>
              <li>Medical dates, allergies, dietary notes, emergency contacts</li>
              <li>Family relationships and group/patrol memberships</li>
              <li>Calendar feed, login link, and any pending invite</li>
              <li>BSA ID and import provenance</li>
            </ul>
          </div>
          <div>
            <p className="font-medium">Kept anonymized (purged after the retention window):</p>
            <ul className="mt-1 list-disc pl-5 text-muted-foreground">
              <li>Event attendance and activity totals</li>
              <li>Advancement and position history</li>
            </ul>
          </div>
        </div>

        <div className="space-y-2">
          <Label htmlFor="purge-confirm">
            Type <span className="font-semibold">{fullName}</span> to confirm
          </Label>
          <Input
            id="purge-confirm"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            placeholder={fullName}
            autoComplete="off"
          />
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => handleOpenChange(false)}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={handlePurge}
            disabled={!armed || purge.isPending}
          >
            {purge.isPending ? "Deleting…" : "Delete permanently"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
