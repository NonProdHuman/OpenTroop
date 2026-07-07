"use client"

import Link from "next/link"
import { Award } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { rankSummary } from "@/components/advancement/rank-progress"
import { useMemberAdvancement } from "@/hooks/use-advancement"
import type { AdvancementScout } from "@/types/api"

/** Compact advancement snapshot for one scout: current rank, next-rank progress,
 * and merit-badge count — consumes the member advancement endpoint a parent can
 * access (`/members/{id}/advancement`), not the `report:read`-gated summary. The
 * next-rank % is the first not-yet-earned rank's top-level requirement completion,
 * matching the web rank-card header (`rankSummary`). */
function ScoutSnapshot({ scout }: { scout: AdvancementScout }) {
  const { data: advancement, isLoading } = useMemberAdvancement(scout.member_id)

  const name = scout.nickname
    ? `${scout.first_name} "${scout.nickname}" ${scout.last_name}`
    : `${scout.first_name} ${scout.last_name}`

  // Next rank = first rank the scout has not yet earned (no board-of-review date).
  const nextView = advancement?.ranks.find((v) => v.progress?.completed_date == null)
  const summary = nextView ? rankSummary(nextView) : null
  const percent = summary && summary.total > 0
    ? Math.round((summary.complete / summary.total) * 100)
    : null
  const badgeCount = (advancement?.merit_badges ?? []).filter((b) => b.date_completed != null).length

  return (
    <Card data-testid="scout-advancement">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-base">
          <Award className="h-4 w-4 shrink-0 text-muted-foreground" />
          <Link href={`/members/${scout.member_id}/advancement`} className="hover:underline">
            {name}
          </Link>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <Skeleton className="h-10 w-full" />
        ) : (
          <dl className="grid grid-cols-3 gap-3 text-sm">
            <div>
              <dt className="text-xs text-muted-foreground">Current rank</dt>
              <dd className="font-medium">{scout.current_rank_name ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">
                {nextView ? `Next: ${nextView.rank.name}` : "Next rank"}
              </dt>
              <dd className="font-medium tabular-nums">
                {percent != null ? `${percent}%` : nextView ? "0%" : "Top rank earned"}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">Merit badges</dt>
              <dd className="font-medium tabular-nums">{badgeCount}</dd>
            </div>
          </dl>
        )}
      </CardContent>
    </Card>
  )
}

/** Advancement snapshot per scout in the household. `scouts` comes from the
 * family-scoped `/advancement/scouts` picker (empty/omitted when advancement is
 * disabled for the troop). */
export function FamilyAdvancement({ scouts }: { scouts: AdvancementScout[] }) {
  if (scouts.length === 0) return null
  return (
    <div className="flex flex-col gap-3">
      {scouts.map((scout) => (
        <ScoutSnapshot key={scout.member_id} scout={scout} />
      ))}
    </div>
  )
}
