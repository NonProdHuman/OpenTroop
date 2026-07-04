"use client"

import { Suspense, useEffect } from "react"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { formatMemberName } from "@/lib/format"
import { useAdvancementScouts } from "@/hooks/use-advancement"
import { MemberAdvancementView } from "@/components/advancement/member-advancement-view"
import { ScoutPicker } from "@/components/advancement/scout-picker"
import { PageHeader } from "@/components/page-header"
import { Skeleton } from "@/components/ui/skeleton"

function AdvancementScoutsContent() {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const { data: scouts, isLoading, error } = useAdvancementScouts()

  const requested = searchParams.get("scout")
  // Only trust the URL if it names a scout the caller may actually view.
  const selected =
    requested && scouts?.some((s) => s.member_id === requested) ? requested : null

  const selectScout = (memberId: string) => {
    router.replace(`${pathname}?scout=${memberId}`)
  }

  // The common parent/scout case: exactly one viewable scout — skip the picking.
  useEffect(() => {
    if (!requested && scouts?.length === 1) {
      selectScout(scouts[0].member_id)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [requested, scouts])

  if (error) {
    return (
      <p className="text-muted-foreground text-sm">
        Advancement is not enabled for this troop.
      </p>
    )
  }
  if (isLoading || !scouts) {
    return <Skeleton className="h-32 w-full" />
  }
  if (scouts.length === 0) {
    return (
      <p className="text-muted-foreground text-sm">
        No advancement records to show. Scouts see their own progress here, and
        parents see their scouts&apos; — records for your family will appear once
        they are on the roster.
      </p>
    )
  }

  const selectedScout = scouts.find((s) => s.member_id === selected)

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <ScoutPicker scouts={scouts} selectedId={selected} onSelect={selectScout} />
        {selectedScout?.current_rank_name && (
          <span className="text-muted-foreground text-sm">
            Current rank: {selectedScout.current_rank_name}
          </span>
        )}
      </div>
      {selected ? (
        <MemberAdvancementView memberId={selected} />
      ) : (
        <p className="text-muted-foreground text-sm">
          Choose a scout to view their rank progress and merit badges.
        </p>
      )}
    </div>
  )
}

export default function AdvancementScoutsPage() {
  return (
    <>
      <PageHeader title="Advancement — Scouts" />
      <div className="flex flex-1 flex-col p-4">
        {/* useSearchParams requires a Suspense boundary during prerender */}
        <Suspense fallback={<Skeleton className="h-32 w-full" />}>
          <AdvancementScoutsContent />
        </Suspense>
      </div>
    </>
  )
}
