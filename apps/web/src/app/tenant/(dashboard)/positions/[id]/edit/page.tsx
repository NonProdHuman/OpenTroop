"use client"

import { useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { X, ChevronsUpDown } from "lucide-react"
import { FormField, SectionTitle } from "@/components/form-helpers"
import { PageHeader } from "@/components/page-header"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Separator } from "@/components/ui/separator"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command"
import { cn } from "@/lib/utils"
import { buttonVariants } from "@/components/ui/button"
import {
  usePosition,
  useUpdatePosition,
  usePositionFunctionalRoles,
  useAttachFunctionalRole,
  useDetachFunctionalRole,
} from "@/hooks/use-positions"
import { useFunctionalRoles } from "@/hooks/use-functional-roles"
import type { Position, PositionScope } from "@/types/api"

export default function PositionEditPage() {
  const { id } = useParams<{ id: string }>()
  const { data: position, isLoading } = usePosition(id)

  if (isLoading || !position) {
    return <div className="p-6 text-sm text-muted-foreground">Loading…</div>
  }

  return <PositionEditForm id={id} position={position} />
}

function PositionEditForm({ id, position }: { id: string; position: Position }) {
  const router = useRouter()
  const [name, setName] = useState(position.name)
  const [appliesTo, setAppliesTo] = useState<PositionScope>(position.applies_to)
  const [sortOrder, setSortOrder] = useState(String(position.sort_order))
  const [nameError, setNameError] = useState<string | null>(null)
  const [addRoleOpen, setAddRoleOpen] = useState(false)

  const { data: links = [] } = usePositionFunctionalRoles(id)
  const { data: allRoles = [] } = useFunctionalRoles()

  const updatePosition = useUpdatePosition()
  const attach = useAttachFunctionalRole()
  const detach = useDetachFunctionalRole()

  const linkedIds = new Set(links.map((l) => l.functional_role_id))
  const addableRoles = allRoles.filter((r) => !linkedIds.has(r.id))
  const roleById = new Map(allRoles.map((r) => [r.id, r.name]))

  async function handleSave() {
    if (!name.trim()) { setNameError("Name is required."); return }
    setNameError(null)
    updatePosition.mutate(
      { id, data: { name: name.trim(), applies_to: appliesTo, sort_order: parseInt(sortOrder, 10) || 0 } },
      {
        onSuccess: () => router.push("/positions"),
        onError: (err) => {
          const msg = err instanceof Error ? err.message : ""
          if (msg.includes("409")) setNameError("A position with this slug already exists.")
          else setNameError("Something went wrong — please try again.")
        },
      },
    )
  }

  return (
    <>
      <PageHeader title={`Edit — ${position.name}`}>
        <Button variant="outline" onClick={() => router.push("/positions")}>
          Cancel
        </Button>
        <Button onClick={handleSave} disabled={updatePosition.isPending}>
          {updatePosition.isPending ? "Saving…" : "Save"}
        </Button>
      </PageHeader>

      <div className="max-w-lg mx-auto p-4 md:p-6 space-y-6">
        {nameError && <p className="text-sm text-destructive">{nameError}</p>}

        <SectionTitle>Details</SectionTitle>

        <FormField label="Name" required>
          <Input value={name} onChange={(e) => setName(e.target.value)} />
        </FormField>

        <FormField label="Slug">
          <Input value={position.slug} disabled className="font-mono text-sm opacity-60" />
          <p className="text-xs text-muted-foreground">Slug is set at creation and cannot be changed.</p>
        </FormField>

        <FormField label="Applies to" required>
          <Select value={appliesTo} onValueChange={(v) => setAppliesTo(v as PositionScope)}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="any">Any member</SelectItem>
              <SelectItem value="scout">Scouts only</SelectItem>
              <SelectItem value="adult">Adults only</SelectItem>
            </SelectContent>
          </Select>
        </FormField>

        <FormField label="Sort order">
          <Input
            type="number"
            value={sortOrder}
            onChange={(e) => setSortOrder(e.target.value)}
            min={0}
            className="w-24"
          />
        </FormField>

        <Separator />

        {/* ── Functional role mapping ───────────────────────── */}
        <SectionTitle>Functional Roles</SectionTitle>
        <p className="text-xs text-muted-foreground -mt-2">
          Members holding this position inherit permissions from these functional roles.
        </p>

        <div className="space-y-2">
          {links.length === 0 ? (
            <p className="text-sm text-muted-foreground">No functional roles linked.</p>
          ) : (
            <ul className="divide-y rounded-md border">
              {links.map((link) => (
                <li key={link.id} className="flex items-center justify-between px-3 py-2 text-sm">
                  <span>{roleById.get(link.functional_role_id) ?? link.functional_role_id}</span>
                  <button
                    type="button"
                    onClick={() => detach.mutate({ positionId: id, functionalRoleId: link.functional_role_id })}
                    disabled={detach.isPending}
                    className="text-muted-foreground hover:text-destructive transition-colors disabled:opacity-40"
                    aria-label="Remove functional role"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </li>
              ))}
            </ul>
          )}

          <Popover open={addRoleOpen} onOpenChange={setAddRoleOpen}>
            <PopoverTrigger
              role="combobox"
              aria-expanded={addRoleOpen}
              className={cn(buttonVariants({ variant: "outline", size: "sm" }), "h-7 gap-1.5 text-xs")}
            >
              <ChevronsUpDown className="h-3 w-3" />
              Add functional role…
            </PopoverTrigger>
            <PopoverContent className="w-64 p-0" align="start">
              <Command>
                <CommandInput placeholder="Search roles…" className="h-8" />
                <CommandList>
                  <CommandEmpty>
                    {addableRoles.length === 0
                      ? "All functional roles are already linked."
                      : "No roles found."}
                  </CommandEmpty>
                  <CommandGroup>
                    {addableRoles.map((role) => (
                      <CommandItem
                        key={role.id}
                        value={role.name}
                        onSelect={() => {
                          attach.mutate({ positionId: id, functionalRoleId: role.id })
                          setAddRoleOpen(false)
                        }}
                      >
                        {role.name}
                        {role.is_admin && (
                          <span className="ml-auto text-xs text-muted-foreground">admin</span>
                        )}
                      </CommandItem>
                    ))}
                  </CommandGroup>
                </CommandList>
              </Command>
            </PopoverContent>
          </Popover>
        </div>

        <div className="flex justify-end gap-3 pt-2">
          <Button variant="outline" onClick={() => router.push("/positions")}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={updatePosition.isPending}>
            {updatePosition.isPending ? "Saving…" : "Save changes"}
          </Button>
        </div>
      </div>
    </>
  )
}
