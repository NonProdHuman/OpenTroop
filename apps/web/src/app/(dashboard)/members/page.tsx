"use client"

import { useMemo, useState } from "react"
import { useRouter } from "next/navigation"
import { useMembers } from "@/hooks/use-members"
import { useGroups, usePatrolMemberships } from "@/hooks/use-groups"
import { useRoles } from "@/hooks/use-roles"
import { useRoleAssignments } from "@/hooks/use-role-assignments"
import { buildColumns } from "./columns"
import { MemberFilters } from "./member-filters"
import { MembersTable } from "./members-table"
import { MemberDetailSheet } from "./member-detail-sheet"
import { PageHeader } from "@/components/page-header"
import { Button } from "@/components/ui/button"
import { UserPlus } from "lucide-react"
import type { Member, MemberStatus, MemberType } from "@/types/api"

export default function MembersPage() {
  const router = useRouter()
  const { data: members = [], isLoading: membersLoading } = useMembers()
  const { data: groups = [] } = useGroups()
  const { data: roles = [] } = useRoles()
  const { data: allAssignments = [] } = useRoleAssignments()
  const patrolMap = usePatrolMemberships()

  const patrols = useMemo(() => groups.filter((g) => g.group_type === "patrol"), [groups])

  // Map<memberId, primary role name> — first assignment wins
  const roleMap = useMemo(() => {
    const roleById = new Map(roles.map((r) => [r.id, r.name]))
    const map = new Map<string, string>()
    for (const a of allAssignments) {
      if (!map.has(a.member_id)) {
        const name = roleById.get(a.role_id)
        if (name) map.set(a.member_id, name)
      }
    }
    return map
  }, [roles, allAssignments])

  const [search, setSearch] = useState("")
  const [typeFilter, setTypeFilter] = useState<MemberType[]>([])
  const [statusFilter, setStatusFilter] = useState<MemberStatus[]>(["active"])
  const [patrolFilter, setPatrolFilter] = useState<string | null>(null)
  const [selectedMember, setSelectedMember] = useState<Member | null>(null)
  const [sheetOpen, setSheetOpen] = useState(false)

  const filtered = useMemo(() => {
    return members.filter((m) => {
      if (m.is_deleted) return false
      if (typeFilter.length > 0 && !typeFilter.includes(m.member_type)) return false
      if (statusFilter.length > 0 && !statusFilter.includes(m.membership_status)) return false
      if (patrolFilter !== null) {
        const selectedPatrol = patrols.find((p) => p.id === patrolFilter)
        if (!selectedPatrol || patrolMap.get(m.id)?.id !== selectedPatrol.id) return false
      }
      if (search) {
        const q = search.toLowerCase()
        const fullName = `${m.first_name} ${m.last_name}`.toLowerCase()
        const reverseName = `${m.last_name} ${m.first_name}`.toLowerCase()
        const email = m.email?.toLowerCase() ?? ""
        const nickname = m.nickname?.toLowerCase() ?? ""
        if (
          !fullName.includes(q) &&
          !reverseName.includes(q) &&
          !email.includes(q) &&
          !nickname.includes(q)
        )
          return false
      }
      return true
    })
  }, [members, typeFilter, statusFilter, patrolFilter, patrolMap, patrols, search])

  const columns = useMemo(() => buildColumns(patrolMap, roleMap), [patrolMap, roleMap])

  function toggleType(v: MemberType) {
    setTypeFilter((prev) =>
      prev.includes(v) ? prev.filter((t) => t !== v) : [...prev, v],
    )
  }

  function toggleStatus(v: MemberStatus) {
    setStatusFilter((prev) =>
      prev.includes(v) ? prev.filter((s) => s !== v) : [...prev, v],
    )
  }

  function handleClear() {
    setSearch("")
    setTypeFilter([])
    setStatusFilter([])
    setPatrolFilter(null)
  }

  function handleRowClick(member: Member) {
    setSelectedMember(member)
    setSheetOpen(true)
  }

  return (
    <>
      <PageHeader title={`Members (${filtered.length})`}>
        <Button size="sm" onClick={() => router.push("/members/new")}>
          <UserPlus className="h-4 w-4 mr-2" />
          Add Member
        </Button>
      </PageHeader>

      <div className="flex-1 space-y-4 p-4 md:p-6">
        <MemberFilters
          search={search}
          types={typeFilter}
          statuses={statusFilter}
          patrolId={patrolFilter}
          patrols={patrols}
          onSearchChange={setSearch}
          onTypeToggle={toggleType}
          onStatusToggle={toggleStatus}
          onPatrolChange={setPatrolFilter}
          onClear={handleClear}
        />

        <MembersTable
          data={filtered}
          columns={columns}
          isLoading={membersLoading}
          onRowClick={handleRowClick}
        />
      </div>

      <MemberDetailSheet
        member={selectedMember}
        open={sheetOpen}
        onOpenChange={setSheetOpen}
      />
    </>
  )
}
