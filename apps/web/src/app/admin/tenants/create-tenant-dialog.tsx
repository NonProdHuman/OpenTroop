"use client"

import { Plus } from "lucide-react"
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
import { useCreateTenant } from "@/hooks/use-platform"
import type { TenantProvisioned } from "@/types/api"
import { InviteTokenDisplay } from "../_components/invite-token-display"

const EMPTY = {
  name: "",
  slug: "",
  founder_first_name: "",
  founder_last_name: "",
  founder_email: "",
}

export function CreateTenantDialog() {
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState(EMPTY)
  const [result, setResult] = useState<TenantProvisioned | null>(null)
  const create = useCreateTenant()

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
      const r = await create.mutateAsync({
        name: form.name.trim(),
        slug: form.slug.trim(),
        founder_first_name: form.founder_first_name.trim(),
        founder_last_name: form.founder_last_name.trim(),
        founder_email: form.founder_email.trim() || null,
      })
      setResult(r)
      toast.success(`Provisioned “${r.name}”`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to create tenant")
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger
        render={
          <Button size="sm">
            <Plus className="h-4 w-4" />
            New tenant
          </Button>
        }
      />
      <DialogContent>
        {result ? (
          <>
            <DialogHeader>
              <DialogTitle>“{result.name}” created</DialogTitle>
              <DialogDescription>
                Invite the founding admin ({form.founder_first_name} {form.founder_last_name}) with
                this token.
              </DialogDescription>
            </DialogHeader>
            <InviteTokenDisplay
              token={result.invite_token}
              slug={result.slug}
              expiresAt={result.invite_expires_at}
            />
            <DialogFooter>
              <Button onClick={() => handleOpenChange(false)}>Done</Button>
            </DialogFooter>
          </>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <DialogHeader>
              <DialogTitle>New tenant</DialogTitle>
              <DialogDescription>
                Create a troop and invite its founding administrator.
              </DialogDescription>
            </DialogHeader>

            <div className="grid gap-3">
              <Field label="Troop name">
                <Input
                  required
                  value={form.name}
                  onChange={(e) => set("name", e.target.value)}
                  placeholder="Troop 123"
                />
              </Field>
              <Field label="Slug (subdomain)" hint="lowercase letters, digits, hyphens">
                <Input
                  required
                  pattern="[a-z0-9-]+"
                  value={form.slug}
                  onChange={(e) => set("slug", e.target.value)}
                  placeholder="troop123"
                />
              </Field>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Founder first name">
                  <Input
                    required
                    value={form.founder_first_name}
                    onChange={(e) => set("founder_first_name", e.target.value)}
                  />
                </Field>
                <Field label="Founder last name">
                  <Input
                    required
                    value={form.founder_last_name}
                    onChange={(e) => set("founder_last_name", e.target.value)}
                  />
                </Field>
              </div>
              <Field label="Founder email" hint="optional">
                <Input
                  type="email"
                  value={form.founder_email}
                  onChange={(e) => set("founder_email", e.target.value)}
                  placeholder="founder@example.com"
                />
              </Field>
            </div>

            <DialogFooter>
              <Button type="submit" disabled={create.isPending}>
                {create.isPending ? "Creating…" : "Create tenant"}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  )
}

function Field({
  label,
  hint,
  children,
}: {
  label: string
  hint?: string
  children: React.ReactNode
}) {
  return (
    <label className="grid gap-1.5 text-sm">
      <span className="font-medium">
        {label}
        {hint ? <span className="ml-1 font-normal text-muted-foreground">— {hint}</span> : null}
      </span>
      {children}
    </label>
  )
}
