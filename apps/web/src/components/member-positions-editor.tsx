"use client"

import { useState } from "react"
import { ChevronDown, ChevronRight, Pencil, Plus, Square, Trash2 } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import type { Member, MemberPositionAssignment, Position } from "@/types/api"
import {
  useRemoveMemberPosition,
  useUpdateMemberPositionTerm,
} from "@/hooks/use-member-positions"
import {
  AddPositionDialog,
  EditTermDialog,
  todayISO,
} from "@/components/member-position-dialogs"
import { formatDate } from "@/lib/format"

interface MemberPositionsEditorProps {
  memberId: string
  /** The member's full term history (current + past), from `?current=false`. */
  assignments: MemberPositionAssignment[]
  /** All positions in the tenant. */
  allPositions: Position[]
  /** All members — used to render the assigned-by column. */
  allMembers?: Member[]
  /** Whether the caller holds role:assign; false renders a read-only view. */
  canAssign: boolean
}

/** Sort terms current-first, then by start date descending (unknown starts last). */
function compareTerms(a: MemberPositionAssignment, b: MemberPositionAssignment): number {
  if (a.is_current !== b.is_current) return a.is_current ? -1 : 1
  if (a.start_date === b.start_date) return 0
  if (a.start_date === null) return 1
  if (b.start_date === null) return -1
  return a.start_date < b.start_date ? 1 : -1
}

function TermRow({
  memberId,
  assignment,
  position,
  assignedByName,
  canAssign,
}: {
  memberId: string
  assignment: MemberPositionAssignment
  position: Position
  assignedByName: string | null
  canAssign: boolean
}) {
  const [editOpen, setEditOpen] = useState(false)
  const updateTerm = useUpdateMemberPositionTerm()
  const removeTerm = useRemoveMemberPosition()
  const pending = updateTerm.isPending || removeTerm.isPending

  function handleEndToday() {
    updateTerm.mutate({
      memberId,
      assignmentId: assignment.id,
      data: { end_date: todayISO() },
    })
  }

  return (
    <TableRow className={assignment.is_current ? undefined : "text-muted-foreground"}>
      <TableCell className="font-medium">
        {position.name}
        {assignment.is_current && (
          <Badge variant="secondary" className="ml-2 text-[10px] uppercase">
            Current
          </Badge>
        )}
      </TableCell>
      <TableCell>{formatDate(assignment.start_date) ?? "—"}</TableCell>
      <TableCell>
        {assignment.end_date ? formatDate(assignment.end_date) : "Present"}
      </TableCell>
      <TableCell>{assignedByName ?? "—"}</TableCell>
      {canAssign && (
        <TableCell className="text-right whitespace-nowrap">
          {assignment.is_current && (
            <Button
              variant="ghost"
              size="sm"
              className="h-7 px-2"
              onClick={handleEndToday}
              disabled={pending}
              aria-label={`End ${position.name} term`}
              title="End this term today"
            >
              <Square className="h-3.5 w-3.5" />
            </Button>
          )}
          <Button
            variant="ghost"
            size="sm"
            className="h-7 px-2"
            onClick={() => setEditOpen(true)}
            disabled={pending}
            aria-label={`Edit ${position.name} term dates`}
            title="Edit term dates"
          >
            <Pencil className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 px-2 text-destructive hover:text-destructive"
            onClick={() => removeTerm.mutate({ memberId, assignmentId: assignment.id })}
            disabled={pending}
            aria-label={`Delete ${position.name} term`}
            title="Delete this term (created in error)"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
          {editOpen && (
            <EditTermDialog
              memberId={memberId}
              assignment={assignment}
              positionName={position.name}
              open={editOpen}
              onOpenChange={setEditOpen}
            />
          )}
        </TableCell>
      )}
    </TableRow>
  )
}

export function MemberPositionsEditor({
  memberId,
  assignments,
  allPositions,
  allMembers = [],
  canAssign,
}: MemberPositionsEditorProps) {
  const [addOpen, setAddOpen] = useState(false)
  const [historyOpen, setHistoryOpen] = useState(false)

  const positionById = new Map(allPositions.map((p) => [p.id, p]))
  const memberName = (id: string | null) => {
    if (!id) return null
    const m = allMembers.find((member) => member.id === id)
    return m ? `${m.first_name} ${m.last_name}` : null
  }

  // Default positions (e.g. "Member") are held by everyone — noise here.
  const terms = assignments.filter((a) => {
    const p = positionById.get(a.position_id)
    return p && !p.is_default
  })

  const current = terms
    .filter((a) => a.is_current)
    .sort((a, b) => {
      const pa = positionById.get(a.position_id)!
      const pb = positionById.get(b.position_id)!
      if (pa.sort_order !== pb.sort_order) return pa.sort_order - pb.sort_order
      return pa.name.localeCompare(pb.name)
    })

  const history = [...terms].sort(compareTerms)
  const currentPositionIds = new Set(current.map((a) => a.position_id))
  // Only a *current* term blocks re-assignment; ended terms may recur.
  const addable = allPositions.filter((p) => !currentPositionIds.has(p.id) && !p.is_default)

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-1.5 min-h-[2rem] items-center">
        {current.length === 0 && (
          <span className="text-sm text-muted-foreground">No current positions</span>
        )}
        {current.map((a) => {
          const position = positionById.get(a.position_id)!
          return (
            <Badge
              key={a.id}
              variant="outline"
              title={
                a.start_date ? `Since ${formatDate(a.start_date)}` : undefined
              }
            >
              {position.name}
            </Badge>
          )
        })}
        {canAssign &&
          (allPositions.length === 0 ? (
            <p className="text-xs text-muted-foreground">No positions have been created yet.</p>
          ) : (
            <Button
              variant="outline"
              size="sm"
              className="h-7 gap-1.5 text-xs"
              onClick={() => setAddOpen(true)}
            >
              <Plus className="h-3 w-3" />
              Add position…
            </Button>
          ))}
      </div>

      {terms.length > 0 && (
        <div>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 gap-1 px-1.5 text-xs text-muted-foreground"
            onClick={() => setHistoryOpen((v) => !v)}
            aria-expanded={historyOpen}
          >
            {historyOpen ? (
              <ChevronDown className="h-3.5 w-3.5" />
            ) : (
              <ChevronRight className="h-3.5 w-3.5" />
            )}
            Position history ({history.length})
          </Button>

          {historyOpen && (
            <Table className="mt-1">
              <TableHeader>
                <TableRow>
                  <TableHead>Position</TableHead>
                  <TableHead>Start</TableHead>
                  <TableHead>End</TableHead>
                  <TableHead>Assigned by</TableHead>
                  {canAssign && <TableHead className="sr-only">Actions</TableHead>}
                </TableRow>
              </TableHeader>
              <TableBody>
                {history.map((a) => (
                  <TermRow
                    key={a.id}
                    memberId={memberId}
                    assignment={a}
                    position={positionById.get(a.position_id)!}
                    assignedByName={memberName(a.assigned_by_id)}
                    canAssign={canAssign}
                  />
                ))}
              </TableBody>
            </Table>
          )}
        </div>
      )}

      {canAssign && addOpen && (
        <AddPositionDialog
          memberId={memberId}
          addablePositions={addable}
          open={addOpen}
          onOpenChange={setAddOpen}
        />
      )}
    </div>
  )
}
