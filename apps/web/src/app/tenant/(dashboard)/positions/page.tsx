"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Lock, Pencil, Trash2, ArrowUpDown, ArrowUp, ArrowDown } from "lucide-react"
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
import { usePositions, useDeletePosition, usePositionFunctionalRoles } from "@/hooks/use-positions"
import { useFunctionalRoles } from "@/hooks/use-functional-roles"
import { usePermissions } from "@/hooks/use-session"
import type { Position } from "@/types/api"
import { toast } from "sonner"

const SCOPE_LABELS: Record<string, string> = {
  scout: "Scout",
  adult: "Adult",
  any: "Any",
}

const SCOPE_BADGE: Record<string, string> = {
  scout: "bg-slate-100 text-slate-700 border border-slate-200 dark:bg-slate-800 dark:text-slate-300",
  adult: "bg-amber-50 text-amber-700 border border-amber-200 dark:bg-amber-950 dark:text-amber-300",
  any: "bg-purple-50 text-purple-700 border border-purple-200 dark:bg-purple-950 dark:text-purple-300",
}

function TintBadge({ label, className }: { label: string; className: string }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${className}`}>
      {label}
    </span>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-3">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        {title}
      </h3>
      {children}
    </div>
  )
}

function PositionDetailSheet({
  position,
  open,
  onOpenChange,
}: {
  position: Position | null
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const router = useRouter()
  const [confirmDelete, setConfirmDelete] = useState(false)
  const { has } = usePermissions()
  const { data: links = [] } = usePositionFunctionalRoles(position?.id ?? null)
  const { data: allRoles = [] } = useFunctionalRoles()
  const deletePosition = useDeletePosition()

  if (!position) return null

  const canManage = has("role:manage")
  const roleById = new Map(allRoles.map((r) => [r.id, r.name]))
  const linkedRoles = links.map((l) => roleById.get(l.functional_role_id) ?? l.functional_role_id)

  function handleDelete() {
    if (!confirmDelete) { setConfirmDelete(true); return }
    deletePosition.mutate(position!.id, {
      onSuccess: () => {
        toast.success(`${position!.name} deleted`)
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
            {position.is_system && <Lock className="h-4 w-4 text-muted-foreground" />}
            {position.name}
          </SheetTitle>
          <SheetDescription className="sr-only">Position details</SheetDescription>
          <div className="flex items-center gap-2 mt-1">
            <TintBadge
              label={SCOPE_LABELS[position.applies_to] ?? position.applies_to}
              className={SCOPE_BADGE[position.applies_to] ?? ""}
            />
            {position.is_system && (
              <Badge variant="outline" className="gap-1">
                <Lock className="h-3 w-3" />
                System
              </Badge>
            )}
          </div>
          {canManage && (
            <div className="flex items-center gap-2 pt-1 flex-wrap">
              <Button size="sm" variant="outline" onClick={() => { onOpenChange(false); router.push(`/positions/${position.id}/edit`) }}>
                <Pencil className="h-3.5 w-3.5 mr-1.5" />
                Edit
              </Button>
              {!position.is_system && (
                <Button
                  size="sm"
                  variant={confirmDelete ? "destructive" : "outline"}
                  onClick={handleDelete}
                  disabled={deletePosition.isPending}
                >
                  <Trash2 className="h-3.5 w-3.5 mr-1.5" />
                  {confirmDelete ? "Confirm delete" : "Delete"}
                </Button>
              )}
            </div>
          )}
        </SheetHeader>

        <div className="space-y-6">
          <Section title="Functional Roles">
            {linkedRoles.length === 0 ? (
              <p className="text-sm text-muted-foreground">No functional roles linked.</p>
            ) : (
              <div className="flex flex-wrap gap-1.5">
                {linkedRoles.map((name, i) => (
                  <Badge key={i} variant="outline">{name}</Badge>
                ))}
              </div>
            )}
          </Section>

          <Separator />

          <Section title="Details">
            <div className="grid grid-cols-3 gap-2 text-sm">
              <span className="text-muted-foreground">Slug</span>
              <span className="col-span-2 font-mono text-xs">{position.slug}</span>
            </div>
            <div className="grid grid-cols-3 gap-2 text-sm">
              <span className="text-muted-foreground">Sort order</span>
              <span className="col-span-2">{position.sort_order}</span>
            </div>
          </Section>
        </div>
      </SheetContent>
    </Sheet>
  )
}

export default function PositionsPage() {
  const router = useRouter()
  const { has } = usePermissions()
  const { data: positions = [], isLoading } = usePositions()
  const [selected, setSelected] = useState<Position | null>(null)
  const [sheetOpen, setSheetOpen] = useState(false)

  const canManage = has("role:manage")

  const [sortField, setSortField] = useState<"name" | "applies_to">("name")
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("asc")

  function handleRowClick(p: Position) {
    setSelected(p)
    setSheetOpen(true)
  }

  function handleSort(field: "name" | "applies_to") {
    if (sortField === field) {
      setSortDirection((prev) => (prev === "asc" ? "desc" : "asc"))
    } else {
      setSortField(field)
      setSortDirection("asc")
    }
  }

  const sortedPositions = [...positions].sort((a, b) => {
    let valA = a[sortField] || ""
    let valB = b[sortField] || ""

    if (sortField === "applies_to") {
      valA = SCOPE_LABELS[a.applies_to] ?? a.applies_to
      valB = SCOPE_LABELS[b.applies_to] ?? b.applies_to
    }

    if (valA.toLowerCase() < valB.toLowerCase()) return sortDirection === "asc" ? -1 : 1
    if (valA.toLowerCase() > valB.toLowerCase()) return sortDirection === "asc" ? 1 : -1
    return 0
  })

  return (
    <>
      <PageHeader title="Positions">
        {canManage && (
          <Button size="sm" onClick={() => router.push("/positions/new")}>
            New position
          </Button>
        )}
      </PageHeader>

      <div className="flex-1 p-4 md:p-6">
        {isLoading ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : positions.length === 0 ? (
          <div className="text-center py-12 space-y-2">
            <p className="text-sm font-medium">No positions yet.</p>
            <p className="text-sm text-muted-foreground">
              Positions define the roles members hold — Scoutmaster, Patrol Leader, etc.
            </p>
            {canManage && (
              <Button size="sm" className="mt-2" onClick={() => router.push("/positions/new")}>
                New position →
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
                    onClick={() => handleSort("applies_to")}
                    className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground cursor-pointer select-none hover:text-foreground"
                  >
                    <div className="flex items-center gap-1">
                      Scope
                      {sortField === "applies_to" ? (
                        sortDirection === "asc" ? <ArrowUp className="h-3.5 w-3.5" /> : <ArrowDown className="h-3.5 w-3.5" />
                      ) : (
                        <ArrowUpDown className="h-3.5 w-3.5 text-muted-foreground/50" />
                      )}
                    </div>
                  </th>
                  <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground w-8"></th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {sortedPositions.map((p) => (
                  <tr
                    key={p.id}
                    onClick={() => handleRowClick(p)}
                    className="cursor-pointer hover:bg-muted/40 transition-colors"
                  >
                    <td className="px-4 py-3 font-medium">
                      <div className="flex items-center gap-2">
                        <span>{p.name}</span>
                        {p.is_system && <Lock className="h-3.5 w-3.5 text-muted-foreground shrink-0" />}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <TintBadge
                        label={SCOPE_LABELS[p.applies_to] ?? p.applies_to}
                        className={SCOPE_BADGE[p.applies_to] ?? ""}
                      />
                    </td>
                    <td className="px-4 py-3"></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <PositionDetailSheet
        position={selected}
        open={sheetOpen}
        onOpenChange={setSheetOpen}
      />
    </>
  )
}
