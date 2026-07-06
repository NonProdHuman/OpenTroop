"use client"

import { useParams } from "next/navigation"
import { formatMemberName } from "@/lib/format"
import { useMember } from "@/hooks/use-members"
import { MemberAdvancementView } from "@/components/advancement/member-advancement-view"
import { PageHeader } from "@/components/page-header"

export default function MemberAdvancementPage() {
  const { id } = useParams<{ id: string }>()
  const { data: member } = useMember(id)

  return (
    <>
      <PageHeader
        title={member ? `${formatMemberName(member)} — Advancement` : "Advancement"} />
      <div className="flex flex-1 flex-col p-4">
        <MemberAdvancementView memberId={id} />
      </div>
    </>
  )
}
