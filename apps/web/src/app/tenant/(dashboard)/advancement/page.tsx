"use client"

import Link from "next/link"
import { useMemo } from "react"
import { formatMemberName } from "@/lib/format"
import {
  useAdvancementQueue,
  useMeritBadges,
  useUpdateCompletion,
  useUpdateMemberMeritBadge,
} from "@/hooks/use-advancement"
import { useMembers } from "@/hooks/use-members"
import { usePermissions } from "@/hooks/use-session"
import { PageHeader } from "@/components/page-header"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"

export default function AdvancementQueuePage() {
  const { has, isLoading: permsLoading } = usePermissions()
  const canApprove = has("advancement:approve")
  const { data: queue, isLoading } = useAdvancementQueue(canApprove)
  const { data: members = [] } = useMembers()
  const { data: badges = [] } = useMeritBadges()
  const updateCompletion = useUpdateCompletion()
  const updateBadge = useUpdateMemberMeritBadge()

  const memberName = useMemo(() => {
    const map = new Map(members.map((m) => [m.id, formatMemberName(m)]))
    return (id: string) => map.get(id) ?? "Unknown member"
  }, [members])
  const badgeName = useMemo(() => {
    const map = new Map(badges.map((b) => [b.id, b.name]))
    return (id: string) => map.get(id) ?? "Unknown badge"
  }, [badges])

  if (!permsLoading && !canApprove) {
    return (
      <>
        <PageHeader title="Advancement" />
        <div className="p-4">
          <p className="text-muted-foreground text-sm">
            The approval queue requires the advancement-approver role. Your own progress
            lives on your member page.
          </p>
        </div>
      </>
    )
  }

  const empty =
    queue !== undefined && queue.completions.length === 0 && queue.merit_badges.length === 0

  return (
    <>
      <PageHeader title="Advancement — Approval queue" />
      <div className="flex flex-1 flex-col gap-4 p-4">
        {isLoading && <Skeleton className="h-32 w-full" />}
        {empty && (
          <p className="text-muted-foreground text-sm">
            Nothing waiting for review. Reported requirements and merit badges will appear
            here.
          </p>
        )}
        {queue && queue.completions.length > 0 && (
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Reported requirements</CardTitle>
            </CardHeader>
            <CardContent className="divide-y">
              {queue.completions.map((completion) => (
                <div
                  key={completion.id}
                  className="flex flex-wrap items-center justify-between gap-2 py-2"
                >
                  <div className="min-w-0">
                    <Link
                      className="text-sm font-medium hover:underline"
                      href={`/members/${completion.member_id}/advancement`}
                    >
                      {memberName(completion.member_id)}
                    </Link>
                    <p className="text-muted-foreground text-xs">
                      Completed {completion.date_completed}
                      {completion.note ? ` — ${completion.note}` : ""}
                    </p>
                  </div>
                  <div className="flex items-center gap-1">
                    <Badge variant="secondary">reported</Badge>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={updateCompletion.isPending}
                      onClick={() =>
                        updateCompletion.mutate({
                          id: completion.id,
                          data: { status: "approved" },
                        })
                      }
                    >
                      Approve
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={updateCompletion.isPending}
                      onClick={() =>
                        updateCompletion.mutate({
                          id: completion.id,
                          data: { status: "rejected" },
                        })
                      }
                    >
                      Reject
                    </Button>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        )}
        {queue && queue.merit_badges.length > 0 && (
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Reported merit badges</CardTitle>
            </CardHeader>
            <CardContent className="divide-y">
              {queue.merit_badges.map((record) => (
                <div
                  key={record.id}
                  className="flex flex-wrap items-center justify-between gap-2 py-2"
                >
                  <div className="min-w-0">
                    <Link
                      className="text-sm font-medium hover:underline"
                      href={`/members/${record.member_id}/advancement`}
                    >
                      {memberName(record.member_id)}
                    </Link>
                    <p className="text-muted-foreground text-xs">
                      {badgeName(record.merit_badge_id)}
                      {record.date_completed
                        ? ` — completed ${record.date_completed}`
                        : " — in progress"}
                    </p>
                  </div>
                  <div className="flex items-center gap-1">
                    <Badge variant="secondary">reported</Badge>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={updateBadge.isPending}
                      onClick={() =>
                        updateBadge.mutate({ id: record.id, data: { status: "approved" } })
                      }
                    >
                      Approve
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={updateBadge.isPending}
                      onClick={() =>
                        updateBadge.mutate({ id: record.id, data: { status: "rejected" } })
                      }
                    >
                      Reject
                    </Button>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        )}
      </div>
    </>
  )
}
