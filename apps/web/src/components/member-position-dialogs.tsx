"use client"

import { useState } from "react"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { FormField } from "@/components/form-helpers"
import type { MemberPositionAssignment, Position } from "@/types/api"
import {
  useAssignMemberPosition,
  useUpdateMemberPositionTerm,
} from "@/hooks/use-member-positions"
import { cn } from "@/lib/utils"

/** Today as an ISO date in the user's local timezone (en-CA formats as YYYY-MM-DD). */
export function todayISO(): string {
  return new Intl.DateTimeFormat("en-CA").format(new Date())
}

export function AddPositionDialog({
  memberId,
  addablePositions,
  open,
  onOpenChange,
}: {
  memberId: string
  /** Positions the member does not currently hold. */
  addablePositions: Position[]
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const assignPosition = useAssignMemberPosition()
  const [selected, setSelected] = useState<Position | null>(null)
  const [startDate, setStartDate] = useState(todayISO)
  const [endDate, setEndDate] = useState("")

  function reset() {
    setSelected(null)
    setStartDate(todayISO())
    setEndDate("")
  }

  function handleOpenChange(next: boolean) {
    if (!next) reset()
    onOpenChange(next)
  }

  function handleSave() {
    if (!selected) return
    assignPosition.mutate(
      {
        memberId,
        positionId: selected.id,
        startDate: startDate || null,
        endDate: endDate || null,
      },
      { onSuccess: () => handleOpenChange(false) },
    )
  }

  const invalidRange = Boolean(startDate && endDate && endDate < startDate)

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Add position</DialogTitle>
          <DialogDescription>
            Start a term. Leave the end date empty for a current position, or set both
            dates to record a past term.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <FormField label="Position" required>
            <Command className="rounded-md border">
              <CommandInput placeholder="Search positions…" className="h-8" />
              <CommandList className="max-h-40">
                <CommandEmpty>
                  {addablePositions.length === 0
                    ? "All positions are already held."
                    : "No positions found."}
                </CommandEmpty>
                <CommandGroup>
                  {addablePositions.map((position) => (
                    <CommandItem
                      key={position.id}
                      value={position.name}
                      onSelect={() => setSelected(position)}
                      className={cn("gap-2", selected?.id === position.id && "font-semibold")}
                      aria-selected={selected?.id === position.id}
                    >
                      <span>{position.name}</span>
                      <span className="ml-auto text-xs text-muted-foreground capitalize">
                        {position.applies_to}
                      </span>
                    </CommandItem>
                  ))}
                </CommandGroup>
              </CommandList>
            </Command>
          </FormField>

          <div className="grid grid-cols-2 gap-3">
            <FormField label="Start date">
              <Input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                aria-label="Start date"
              />
            </FormField>
            <FormField label="End date" hint="Empty = current">
              <Input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                aria-label="End date"
              />
            </FormField>
          </div>

          {invalidRange && (
            <p className="text-sm text-destructive">End date must be on or after start date.</p>
          )}
          {assignPosition.isError && (
            <p className="text-sm text-destructive">
              Couldn&apos;t add the position — they may already hold a current term for it.
            </p>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => handleOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={handleSave}
            disabled={!selected || invalidRange || assignPosition.isPending}
          >
            {assignPosition.isPending ? "Adding…" : "Add position"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export function EditTermDialog({
  memberId,
  assignment,
  positionName,
  open,
  onOpenChange,
}: {
  memberId: string
  assignment: MemberPositionAssignment
  positionName: string
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const updateTerm = useUpdateMemberPositionTerm()
  const [startDate, setStartDate] = useState(assignment.start_date ?? "")
  const [endDate, setEndDate] = useState(assignment.end_date ?? "")

  function handleSave() {
    updateTerm.mutate(
      {
        memberId,
        assignmentId: assignment.id,
        data: {
          start_date: startDate || null,
          // Clearing the end date reopens the term (makes it current again).
          end_date: endDate || null,
        },
      },
      { onSuccess: () => onOpenChange(false) },
    )
  }

  const invalidRange = Boolean(startDate && endDate && endDate < startDate)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Edit term — {positionName}</DialogTitle>
          <DialogDescription>
            Adjust the term&apos;s dates. Clearing the end date reopens the term.
          </DialogDescription>
        </DialogHeader>

        <div className="grid grid-cols-2 gap-3">
          <FormField label="Start date">
            <Input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              aria-label="Start date"
            />
          </FormField>
          <FormField label="End date" hint="Empty = current">
            <Input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              aria-label="End date"
            />
          </FormField>
        </div>

        {invalidRange && (
          <p className="text-sm text-destructive">End date must be on or after start date.</p>
        )}
        {updateTerm.isError && (
          <p className="text-sm text-destructive">Couldn&apos;t save the dates — please try again.</p>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={invalidRange || updateTerm.isPending}>
            {updateTerm.isPending ? "Saving…" : "Save dates"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
