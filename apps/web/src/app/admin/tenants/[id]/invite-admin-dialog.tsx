"use client"

import { UserPlus } from "lucide-react"
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
import { useInviteTenantAdmin, useTenant } from "@/hooks/use-platform"
import type { TenantAdminInviteResult } from "@/types/api"
import { InviteTokenDisplay } from "../../_components/invite-token-display"

const EMPTY = { first_name: "", last_name: "", email: "" }

export function InviteAdminDialog({ tenantId }: { tenantId: string }) {
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState(EMPTY)
  const [result, setResult] = useState<TenantAdminInviteResult | null>(null)
  const invite = useInviteTenantAdmin(tenantId)
  const { data: tenant } = useTenant(tenantId)

  function set(field: keyof typeof EMPTY, value: string) {
    setForm((f) => ({ ...f, [field]: value }))
  }

  function handleOpenChange(next: boolean) {
    setOpen(next)
    if (!next) {
      setForm(EMPTY)
      setResult(null)
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    try {
      const r = await invite.mutateAsync({
        first_name: form.first_name.trim(),
        last_name: form.last_name.trim(),
        email: form.email.trim() || null,
      })
      setResult(r)
      toast.success("Admin invited")
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to invite admin")
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger
        render={
          <Button size="sm" variant="outline">
            <UserPlus className="h-4 w-4" />
            Invite admin
          </Button>
        }
      />
      <DialogContent>
        {result ? (
          <>
            <DialogHeader>
              <DialogTitle>Admin invited</DialogTitle>
              <DialogDescription>
                Send {form.first_name} {form.last_name} this token to claim their account.
              </DialogDescription>
            </DialogHeader>
            <InviteTokenDisplay
              token={result.token}
              slug={tenant?.slug ?? ""}
              expiresAt={result.expires_at}
            />
            <DialogFooter>
              <Button onClick={() => handleOpenChange(false)}>Done</Button>
            </DialogFooter>
          </>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <DialogHeader>
              <DialogTitle>Invite an administrator</DialogTitle>
              <DialogDescription>
                Adds an unclaimed admin member to this tenant and returns a claim token.
              </DialogDescription>
            </DialogHeader>

            <div className="grid grid-cols-2 gap-3">
              <label className="grid gap-1.5 text-sm">
                <span className="font-medium">First name</span>
                <Input
                  required
                  value={form.first_name}
                  onChange={(e) => set("first_name", e.target.value)}
                />
              </label>
              <label className="grid gap-1.5 text-sm">
                <span className="font-medium">Last name</span>
                <Input
                  required
                  value={form.last_name}
                  onChange={(e) => set("last_name", e.target.value)}
                />
              </label>
            </div>
            <label className="grid gap-1.5 text-sm">
              <span className="font-medium">
                Email <span className="font-normal text-muted-foreground">— optional</span>
              </span>
              <Input
                type="email"
                value={form.email}
                onChange={(e) => set("email", e.target.value)}
                placeholder="admin@example.com"
              />
            </label>

            <DialogFooter>
              <Button type="submit" disabled={invite.isPending}>
                {invite.isPending ? "Inviting…" : "Invite admin"}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  )
}
