"use client"

import { useMemo } from "react"
import { PageHeader } from "@/components/page-header"
import { Skeleton } from "@/components/ui/skeleton"
import { formatMemberName } from "@/lib/format"
import { useFamily } from "@/hooks/use-family"
import { useAdvancementScouts } from "@/hooks/use-advancement"
import type { Member } from "@/types/api"
import { FamilyMemberCard } from "./family-member-card"
import { FamilyEvents } from "./family-events"
import { FamilyAdvancement } from "./family-advancement"

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        {title}
      </h2>
      {children}
    </section>
  )
}

function FamilyContent() {
  const { data: family, isLoading, error } = useFamily()
  // Family-scoped picker; errors (404) when advancement is disabled — treat as none.
  const { data: scouts, error: scoutsError } = useAdvancementScouts()
  const availableScouts = useMemo(
    () => (scoutsError ? [] : (scouts ?? [])),
    [scouts, scoutsError],
  )

  const patrolByMember = useMemo(() => {
    const map = new Map<string, string>()
    for (const s of availableScouts) {
      if (s.patrol_name) map.set(s.member_id, s.patrol_name)
    }
    return map
  }, [availableScouts])

  if (error) {
    return (
      <p className="text-sm text-muted-foreground">
        We couldn&apos;t load your family right now. Please try again.
      </p>
    )
  }
  if (isLoading || !family) {
    return <Skeleton className="h-40 w-full" />
  }

  // Household scouts (from /advancement/scouts) restricted to this household.
  const householdMemberIds = new Set(family.members.map((m) => m.id))
  const householdScouts = availableScouts.filter((s) => householdMemberIds.has(s.member_id))

  const members = [...family.members].sort((a: Member, b: Member) =>
    formatMemberName(a).localeCompare(formatMemberName(b)),
  )

  return (
    <div className="flex flex-col gap-8">
      <Section title="Household">
        <div className="grid gap-3 sm:grid-cols-2">
          {members.map((member) => (
            <FamilyMemberCard
              key={member.id}
              member={member}
              patrolName={patrolByMember.get(member.id)}
            />
          ))}
        </div>
      </Section>

      <Section title="Upcoming events">
        <FamilyEvents />
      </Section>

      {householdScouts.length > 0 && (
        <Section title="Advancement">
          <FamilyAdvancement scouts={householdScouts} />
        </Section>
      )}
    </div>
  )
}

export default function FamilyPage() {
  return (
    <>
      <PageHeader title="My Family" />
      <div className="flex flex-1 flex-col p-4">
        <FamilyContent />
      </div>
    </>
  )
}
