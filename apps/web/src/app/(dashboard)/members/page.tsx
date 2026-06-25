"use client"

import { useMemo, useState } from "react"
import { useMembers } from "@/hooks/use-members"
import { buildColumns } from "./columns"
import { MemberFilters } from "./member-filters"
import { MembersTable } from "./members-table"
import { MemberDetailSheet } from "./member-detail-sheet"
import { PageHeader } from "@/components/page-header"
import { Button } from "@/components/ui/button"
import { UserPlus } from "lucide-react"
import type { Member, MemberStatus, MemberType } from "@/types/api"

export default function MembersPage() {
  const { data: members = [], isLoading: membersLoading } = useMembers()

  const [search, setSearch] = useState("")
  const [typeFilter, setTypeFilter] = useState<MemberType[]>([])
  const [statusFilter, setStatusFilter] = useState<MemberStatus[]>(["active"])
  const [selectedMember, setSelectedMember] = useState<Member | null>(null)
  const [sheetOpen, setSheetOpen] = useState(false)

  const filtered = useMemo(() => {
    return members.filter((m) => {
      if (m.is_deleted) return false

      if (typeFilter.length > 0 && !typeFilter.includes(m.member_type)) return false
      if (statusFilter.length > 0 && !statusFilter.includes(m.membership_status))
        return false

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
  }, [members, typeFilter, statusFilter, search])

  const columns = useMemo(() => buildColumns(), [])

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
  }

  function handleRowClick(member: Member) {
    setSelectedMember(member)
    setSheetOpen(true)
  }

  return (
    <>
      <PageHeader title={`Members (${filtered.length})`}>
        <Button size="sm">
          <UserPlus className="h-4 w-4 mr-2" />
          Add Member
        </Button>
      </PageHeader>

      <div className="flex-1 space-y-4 p-4 md:p-6">
        <MemberFilters
          search={search}
          types={typeFilter}
          statuses={statusFilter}
          onSearchChange={setSearch}
          onTypeToggle={toggleType}
          onStatusToggle={toggleStatus}
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
