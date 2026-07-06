"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Lock, Pencil, Trash2, ShieldCheck, ArrowUpDown, ArrowUp, ArrowDown } from "lucide-react"
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { PageHeader } from "@/components/page-header"
import { Section } from "@/components/detail-helpers"
import {
  useFunctionalRoles,
  useDeleteFunctionalRole,
  useFunctionalRolePermissions,
} from "@/hooks/use-functional-roles"
import { usePermissions } from "@/hooks/use-session"
import type { FunctionalRole, Permission } from "@/types/api"
import { toast } from "sonner"

const PERMISSION_LABELS: Record<Permission, string> = {
  "member:read": "Member — View",
  "member:write": "Member — Edit",
  "member:read_medical": "Member — View Medical",
  "member:write_medical": "Member — Edit Medical",
  "member:read_contact": "Member — View Contact",
  "member:delete": "Member — Delete",
  "event:read": "Event — View",
  "event:create": "Event — Create",
  "event:write": "Event — Edit",
  "event:delete": "Event — Delete",
  "event:manage_attendance": "Event — Attendance",
  "advancement:read": "Advancement — View",
  "advancement:record": "Advancement — Record",
  "advancement:approve": "Advancement — Approve",
  "finance:read": "Finance — View",
  "finance:write": "Finance — Edit",
  "role:assign": "Roles — Assign Positions",
  "role:manage": "Roles — Manage Roles",
  "communication:send_troop": "Communication — Troop",
  "communication:send_patrol": "Communication — Patrol",
  "report:read": "Reports — View",
  "photo:read": "Photos — View",
  "photo:upload": "Photos — Add",
  "photo:moderate": "Photos — Moderate",
}

const PERM_DOMAINS = [
  { label: "Member", prefix: "member:" },
  { label: "Event", prefix: "event:" },
  { label: "Advancement", prefix: "advancement:" },
  { label: "Finance", prefix: "finance:" },
  { label: "Roles", prefix: "role:" },
  { label: "Communication", prefix: "communication:" },
  { label: "Reports", prefix: "report:" },
  { label: "Photos", prefix: "photo:" },
]

function FunctionalRoleDetailSheet({
  role,
  open,
  onOpenChange,
}: {
  role: FunctionalRole | null
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const router = useRouter()
  const [confirmDelete, setConfirmDelete] = useState(false)
  const { has } = usePermissions()
  const { data: perms = [] } = useFunctionalRolePermissions(role?.id ?? null)
  const deleteRole = useDeleteFunctionalRole()

  if (!role) return null

  const canManage = has("role:manage")
  const permSet = new Set(perms.map((p) => p.permission))

  function handleDelete() {
    if (!confirmDelete) { setConfirmDelete(true); return }
    deleteRole.mutate(role!.id, {
      onSuccess: () => {
        toast.success(`${role!.name} deleted`)
        onOpenChange(false)
      },
      onError: () => toast.error("Delete failed — please try again."),
    })
  }

  return (
    <Sheet open={open} onOpenChange={(v) => { setConfirmDelete(false); onOpenChange(v) }}>
      <SheetContent className="w-full sm:max-w-md overflow-y-auto">
        <SheetHeader className="pb-4">
          <SheetTitle className="text-xl flex items-center gap-2">
            {role.is_system && <Lock className="h-4 w-4 text-muted-foreground" />}
            {role.name}
          </SheetTitle>
          <SheetDescription className="sr-only">Functional role details</SheetDescription>
          <div className="flex items-center gap-2 mt-1">
            {role.is_admin && (
              <Badge className="gap-1 bg-amber-500 hover:bg-amber-500">
                <ShieldCheck className="h-3 w-3" />
                Administrator
              </Badge>
            )}
            {role.is_system && (
              <Badge variant="outline" className="gap-1">
                <Lock className="h-3 w-3" />
                System
              </Badge>
            )}
          </div>
          {canManage && (
            <div className="flex items-center gap-2 pt-1 flex-wrap">
              <Button
                size="sm"
                variant="outline"
                onClick={() => { onOpenChange(false); router.push(`/functional-roles/${role.id}/edit`) }}
              >
                <Pencil className="h-3.5 w-3.5 mr-1.5" />
                Edit
              </Button>
              {!role.is_system && (
                <Button
                  size="sm"
                  variant={confirmDelete ? "destructive" : "outline"}
                  onClick={handleDelete}
                  disabled={deleteRole.isPending}
                >
                  <Trash2 className="h-3.5 w-3.5 mr-1.5" />
                  {confirmDelete ? "Confirm delete" : "Delete"}
                </Button>
              )}
            </div>
          )}
        </SheetHeader>

        <div className="space-y-6">
          {role.is_admin ? (
            <Section title="Permissions">
              <p className="text-sm text-muted-foreground">
                This functional role grants <strong>all permissions</strong> (administrator shortcut).
              </p>
            </Section>
          ) : (
            <Section title="Permissions">
              {perms.length === 0 ? (
                <p className="text-sm text-muted-foreground">No permissions granted.</p>
              ) : (
                <div className="space-y-3">
                  {PERM_DOMAINS.map(({ label, prefix }) => {
                    const domainPerms = Object.entries(PERMISSION_LABELS).filter(
                      ([p]) => p.startsWith(prefix) && permSet.has(p as Permission),
                    )
                    if (domainPerms.length === 0) return null
                    return (
                      <div key={prefix}>
                        <p className="text-xs font-medium text-muted-foreground mb-1">{label}</p>
                        <div className="flex flex-wrap gap-1">
                          {domainPerms.map(([, lbl]) => (
                            <Badge key={lbl} variant="secondary" className="text-xs">
                              {lbl}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </Section>
          )}

          <Separator />

          <Section title="Details">
            <div className="grid grid-cols-3 gap-2 text-sm">
              <span className="text-muted-foreground">Slug</span>
              <span className="col-span-2 font-mono text-xs">{role.slug}</span>
            </div>
          </Section>
        </div>
      </SheetContent>
    </Sheet>
  )
}

export default function FunctionalRolesPage() {
  const router = useRouter()
  const { has } = usePermissions()
  const { data: roles = [], isLoading } = useFunctionalRoles()
  const [selected, setSelected] = useState<FunctionalRole | null>(null)
  const [sheetOpen, setSheetOpen] = useState(false)

  const [sortField, setSortField] = useState<"name" | "type">("name")
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("asc")

  function handleRowClick(r: FunctionalRole) {
    setSelected(r)
    setSheetOpen(true)
  }

  function handleSort(field: "name" | "type") {
    if (sortField === field) {
      setSortDirection((prev) => (prev === "asc" ? "desc" : "asc"))
    } else {
      setSortField(field)
      setSortDirection("asc")
    }
  }

  const sortedRoles = [...roles].sort((a, b) => {
    let valA = ""
    let valB = ""

    if (sortField === "name") {
      valA = a.name
      valB = b.name
    } else if (sortField === "type") {
      valA = a.is_admin ? "Admin" : "Standard"
      valB = b.is_admin ? "Admin" : "Standard"
    }

    if (valA.toLowerCase() < valB.toLowerCase()) return sortDirection === "asc" ? -1 : 1
    if (valA.toLowerCase() > valB.toLowerCase()) return sortDirection === "asc" ? 1 : -1
    return 0
  })
  const canManage = has("role:manage")

  return (
    <>
      <PageHeader title="Functional Roles">
        {canManage && (
          <Button size="sm" onClick={() => router.push("/functional-roles/new")}>
            New role
          </Button>
        )}
      </PageHeader>

      <div className="flex-1 p-4 md:p-6">
        {isLoading ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : roles.length === 0 ? (
          <div className="text-center py-12 space-y-2">
            <p className="text-sm font-medium">No functional roles yet.</p>
            <p className="text-sm text-muted-foreground">
              Functional roles bundle permissions and are linked to positions.
            </p>
            {canManage && (
              <Button size="sm" className="mt-2" onClick={() => router.push("/functional-roles/new")}>
                New role →
              </Button>
            )}
          </div>
        ) : (
          <div className="rounded-md border overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/40">
                  <th
                    onClick={() => handleSort("name")}
                    className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground cursor-pointer select-none hover:text-foreground"
                  >
                    <div className="flex items-center gap-1">
                      Name
                      {sortField === "name" ? (
                        sortDirection === "asc" ? <ArrowUp className="h-3.5 w-3.5" /> : <ArrowDown className="h-3.5 w-3.5" />
                      ) : (
                        <ArrowUpDown className="h-3.5 w-3.5 text-muted-foreground/50" />
                      )}
                    </div>
                  </th>
                  <th
                    onClick={() => handleSort("type")}
                    className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground cursor-pointer select-none hover:text-foreground"
                  >
                    <div className="flex items-center gap-1">
                      Type
                      {sortField === "type" ? (
                        sortDirection === "asc" ? <ArrowUp className="h-3.5 w-3.5" /> : <ArrowDown className="h-3.5 w-3.5" />
                      ) : (
                        <ArrowUpDown className="h-3.5 w-3.5 text-muted-foreground/50" />
                      )}
                    </div>
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {sortedRoles.map((r) => (
                  <tr
                    key={r.id}
                    onClick={() => handleRowClick(r)}
                    className="cursor-pointer hover:bg-muted/40 transition-colors"
                  >
                    <td className="px-4 py-3 font-medium">
                      <div className="flex items-center gap-2">
                        <span>{r.name}</span>
                        {r.is_system && <Lock className="h-3.5 w-3.5 text-muted-foreground shrink-0" />}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      {r.is_admin && (
                        <Badge className="gap-1 bg-amber-500 hover:bg-amber-500 text-white text-xs">
                          <ShieldCheck className="h-3 w-3" />
                          Admin
                        </Badge>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <FunctionalRoleDetailSheet
        role={selected}
        open={sheetOpen}
        onOpenChange={setSheetOpen}
      />
    </>
  )
}
