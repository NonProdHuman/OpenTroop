"use client"

import { useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { ShieldCheck } from "lucide-react"
import { SectionTitle } from "@/components/form-helpers"
import { PageHeader } from "@/components/page-header"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Separator } from "@/components/ui/separator"
import {
  useFunctionalRole,
  useUpdateFunctionalRole,
  useFunctionalRolePermissions,
  useGrantFunctionalRolePermission,
  useRevokeFunctionalRolePermission,
} from "@/hooks/use-functional-roles"
import type { FunctionalRole, Permission } from "@/types/api"

const ALL_PERMISSIONS: Permission[] = [
  "member:read",
  "member:write",
  "member:read_medical",
  "member:write_medical",
  "member:read_contact",
  "member:delete",
  "event:read",
  "event:create",
  "event:write",
  "event:delete",
  "event:manage_attendance",
  "advancement:read",
  "advancement:record",
  "advancement:approve",
  "finance:read",
  "finance:write",
  "role:assign",
  "role:manage",
  "communication:send_troop",
  "communication:send_patrol",
  "report:read",
]

const PERM_GROUPS: { label: string; perms: Permission[] }[] = [
  {
    label: "Members",
    perms: [
      "member:read",
      "member:write",
      "member:read_medical",
      "member:write_medical",
      "member:read_contact",
      "member:delete",
    ],
  },
  {
    label: "Events",
    perms: [
      "event:read",
      "event:create",
      "event:write",
      "event:delete",
      "event:manage_attendance",
    ],
  },
  {
    label: "Advancement",
    perms: ["advancement:read", "advancement:record", "advancement:approve"],
  },
  {
    label: "Finance",
    perms: ["finance:read", "finance:write"],
  },
  {
    label: "Roles",
    perms: ["role:assign", "role:manage"],
  },
  {
    label: "Communication",
    perms: ["communication:send_troop", "communication:send_patrol"],
  },
  {
    label: "Reports",
    perms: ["report:read"],
  },
]

const PERM_LABELS: Record<Permission, string> = {
  "member:read": "View members",
  "member:write": "Edit members",
  "member:read_medical": "View medical info",
  "member:write_medical": "Edit medical info",
  "member:read_contact": "View contact info",
  "member:delete": "Delete members",
  "event:read": "View events",
  "event:create": "Create events",
  "event:write": "Edit events",
  "event:delete": "Delete events",
  "event:manage_attendance": "Manage attendance",
  "advancement:read": "View advancement",
  "advancement:record": "Record advancement",
  "advancement:approve": "Approve advancement",
  "finance:read": "View finances",
  "finance:write": "Edit finances",
  "role:assign": "Assign positions to members",
  "role:manage": "Manage roles & positions",
  "communication:send_troop": "Send troop-wide messages",
  "communication:send_patrol": "Send patrol messages",
  "report:read": "View reports",
}

void ALL_PERMISSIONS // used for exhaustive mapping above

export default function FunctionalRoleEditPage() {
  const { id } = useParams<{ id: string }>()
  const { data: role, isLoading } = useFunctionalRole(id)

  if (isLoading || !role) {
    return <div className="p-6 text-sm text-muted-foreground">Loading…</div>
  }

  return <FunctionalRoleEditForm id={id} role={role} />
}

function FunctionalRoleEditForm({ id, role }: { id: string; role: FunctionalRole }) {
  const router = useRouter()
  const [name, setName] = useState(role.name)
  const [nameError, setNameError] = useState<string | null>(null)

  const { data: perms = [] } = useFunctionalRolePermissions(id)
  const updateRole = useUpdateFunctionalRole()
  const grant = useGrantFunctionalRolePermission()
  const revoke = useRevokeFunctionalRolePermission()

  const permSet = new Set(perms.map((p) => p.permission))
  const isBusy = grant.isPending || revoke.isPending

  function handleToggle(perm: Permission, checked: boolean) {
    if (checked) {
      grant.mutate({ roleId: id, permission: perm })
    } else {
      revoke.mutate({ roleId: id, permission: perm })
    }
  }

  async function handleSave() {
    if (!name.trim()) { setNameError("Name is required."); return }
    setNameError(null)
    updateRole.mutate(
      { id, data: { name: name.trim() } },
      {
        onSuccess: () => router.push("/functional-roles"),
        onError: () => setNameError("Something went wrong — please try again."),
      },
    )
  }

  return (
    <>
      <PageHeader title={`Edit — ${role.name}`}>
        <Button variant="outline" onClick={() => router.push("/functional-roles")}>
          Cancel
        </Button>
        <Button onClick={handleSave} disabled={updateRole.isPending}>
          {updateRole.isPending ? "Saving…" : "Save"}
        </Button>
      </PageHeader>

      <div className="max-w-lg mx-auto p-4 md:p-6 space-y-6">
        {nameError && <p className="text-sm text-destructive">{nameError}</p>}

        <SectionTitle>Details</SectionTitle>

        <div className="space-y-1.5">
          <Label>
            Name <span className="text-destructive">*</span>
          </Label>
          <Input value={name} onChange={(e) => setName(e.target.value)} />
        </div>

        <div className="space-y-1.5">
          <Label>Slug</Label>
          <Input value={role.slug} disabled className="font-mono text-sm opacity-60" />
          <p className="text-xs text-muted-foreground">Slug is set at creation and cannot be changed.</p>
        </div>

        <Separator />

        {/* ── Permissions ────────────────────────────────────── */}
        <SectionTitle>Permissions</SectionTitle>

        {role.is_admin ? (
          <div className="flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 dark:border-amber-800 dark:bg-amber-950/30 px-4 py-3 text-sm">
            <ShieldCheck className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" />
            <p className="text-amber-800 dark:text-amber-200">
              This functional role grants <strong>all permissions</strong> (administrator shortcut).
              Individual permissions cannot be edited here.
            </p>
          </div>
        ) : (
          <div className="space-y-5">
            {PERM_GROUPS.map(({ label, perms: groupPerms }) => (
              <div key={label}>
                <p className="text-xs font-semibold text-muted-foreground mb-2 uppercase tracking-wide">
                  {label}
                </p>
                <div className="space-y-1.5">
                  {groupPerms.map((perm) => (
                    <label key={perm} className="flex items-center gap-2.5 text-sm cursor-pointer select-none">
                      <input
                        type="checkbox"
                        checked={permSet.has(perm)}
                        onChange={(e) => handleToggle(perm, e.target.checked)}
                        disabled={isBusy}
                        className="rounded"
                      />
                      {PERM_LABELS[perm]}
                    </label>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="flex justify-end gap-3 pt-2">
          <Button variant="outline" onClick={() => router.push("/functional-roles")}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={updateRole.isPending}>
            {updateRole.isPending ? "Saving…" : "Save changes"}
          </Button>
        </div>
      </div>
    </>
  )
}
