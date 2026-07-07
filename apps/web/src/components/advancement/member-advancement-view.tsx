"use client"

import { useMemo, useState } from "react"
import {
  useCreateCompletion,
  useCreateMemberMeritBadge,
  useMemberAdvancement,
  useMeritBadges,
  useRevokeCompletion,
  useUpdateCompletion,
  useUpdateRankProgress,
} from "@/hooks/use-advancement"
import { usePermissions, useSession } from "@/hooks/use-session"
import { useTenantSettings } from "@/hooks/use-tenant-settings"
import { MetricMeter, rankSummary, statusBadgeVariant } from "./rank-progress"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import type { MemberRankView, RequirementProgress } from "@/types/api"

function today(): string {
  return new Date().toISOString().slice(0, 10)
}

function RequirementRow({
  memberId,
  entry,
  canRecord,
  canApprove,
  canSelfReport,
  locked,
  earned,
}: {
  memberId: string
  entry: RequirementProgress
  canRecord: boolean
  canApprove: boolean
  canSelfReport: boolean
  /** Rank awarded — completion history is read-only (#256 D1). */
  locked: boolean
  /** Rank earned (BoR passed) — self-report closes; chairs may still correct. */
  earned: boolean
}) {
  const createCompletion = useCreateCompletion(memberId)
  const updateCompletion = useUpdateCompletion()
  const revokeCompletion = useRevokeCompletion()
  const [markDate, setMarkDate] = useState(today())
  const req = entry.requirement
  const isContainer = req.letter === "" && entry.completion === null && entry.metrics_progress.length === 0 && !canRecord
  const indent = req.letter !== ""
  const completion = entry.completion
  const mayRecordHere = !locked && (canRecord || (canSelfReport && !earned))

  return (
    <div className={`flex flex-col gap-1 py-2 ${indent ? "pl-6" : ""}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex min-w-0 items-start gap-2">
          <span
            className={`mt-0.5 inline-flex h-5 w-8 shrink-0 items-center justify-center rounded text-xs font-semibold ${
              entry.is_complete
                ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400"
                : "bg-muted text-muted-foreground"
            }`}
          >
            {req.label}
          </span>
          <p className="text-sm leading-5">{req.text}</p>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          {completion && (
            <Badge variant={statusBadgeVariant(completion.status)}>
              {completion.status}
              {completion.recorded_via === "auto" ? " · auto" : ""}
            </Badge>
          )}
          {completion && completion.status === "reported" && canApprove && !locked && (
            <>
              <Button
                size="sm"
                variant="outline"
                onClick={() =>
                  updateCompletion.mutate({ id: completion.id, data: { status: "approved" } })
                }
              >
                Approve
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() =>
                  updateCompletion.mutate({ id: completion.id, data: { status: "rejected" } })
                }
              >
                Reject
              </Button>
            </>
          )}
          {completion && canApprove && !locked && completion.status !== "reported" && (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => revokeCompletion.mutate(completion.id)}
            >
              Revoke
            </Button>
          )}
          {!completion && !isContainer && mayRecordHere && (
            <>
              <Input
                type="date"
                aria-label={`Completion date for ${req.label}`}
                className="h-8 w-36"
                max={today()}
                value={markDate}
                onChange={(e) => setMarkDate(e.target.value)}
              />
              <Button
                size="sm"
                variant="outline"
                disabled={createCompletion.isPending || !markDate}
                onClick={() =>
                  createCompletion.mutate({ requirement_id: req.id, date_completed: markDate })
                }
              >
                {canRecord ? "Mark complete" : "Report"}
              </Button>
            </>
          )}
        </div>
      </div>
      {completion && (
        <div className="text-muted-foreground flex items-center gap-2 pl-10 text-xs">
          {canRecord && !locked ? (
            <Input
              type="date"
              aria-label={`Edit completion date for ${req.label}`}
              className="h-7 w-36"
              max={today()}
              defaultValue={completion.date_completed}
              onBlur={(e) => {
                const value = e.target.value
                if (value && value !== completion.date_completed) {
                  updateCompletion.mutate({ id: completion.id, data: { date_completed: value } })
                }
              }}
            />
          ) : (
            <span>{completion.date_completed}</span>
          )}
          {completion.note ? <span>— {completion.note}</span> : null}
        </div>
      )}
      {entry.metrics_progress.length > 0 && (
        <div className="flex flex-col gap-1 pl-10">
          {entry.metrics_progress.map((m) => (
            <MetricMeter key={`${m.kind}-${m.window}`} metric={m} />
          ))}
        </div>
      )}
    </div>
  )
}

function RankCard({
  memberId,
  view,
  canRecord,
  canApprove,
  canSelfReport,
}: {
  memberId: string
  view: MemberRankView
  canRecord: boolean
  canApprove: boolean
  canSelfReport: boolean
}) {
  const updateRank = useUpdateRankProgress(memberId)
  const summary = rankSummary(view)
  const earned = view.progress?.completed_date != null
  const awarded = view.progress?.awarded_date != null

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="flex items-center gap-2 text-base">
            {view.rank.name}
            <span className="text-muted-foreground text-xs font-normal">
              v{view.requirement_set.version}
            </span>
            {earned && <Badge data-testid="earned-badge">Earned {view.progress?.completed_date}</Badge>}
            {awarded && (
              <Badge variant="secondary" data-testid="awarded-badge">
                Awarded {view.progress?.awarded_date}
              </Badge>
            )}
            {!earned && view.is_complete && <Badge variant="secondary">Ready for board of review</Badge>}
          </CardTitle>
          <div className="text-muted-foreground text-xs">
            {summary.complete}/{summary.total} requirements
          </div>
        </div>
        {canApprove && (
          <div className="flex flex-wrap items-end gap-3 pt-1">
            {/* The earned (board of review) date is derived from the requirement
                completions — the BoR is itself a requirement (#256 D3) — so there
                is deliberately no manual input for it here. */}
            <div className="flex flex-col gap-1">
              <Label className="text-xs" htmlFor={`coh-${view.rank.id}`}>
                Awarded (Court of Honor)
              </Label>
              <Input
                id={`coh-${view.rank.id}`}
                type="date"
                className="h-8 w-40"
                defaultValue={view.progress?.awarded_date ?? ""}
                onBlur={(e) => {
                  const value = e.target.value || null
                  if (value !== (view.progress?.awarded_date ?? null)) {
                    updateRank.mutate({ rankId: view.rank.id, data: { awarded_date: value } })
                  }
                }}
              />
            </div>
          </div>
        )}
      </CardHeader>
      <CardContent className="divide-y">
        {view.requirements.map((entry) => (
          <RequirementRow
            key={entry.requirement.id}
            memberId={memberId}
            entry={entry}
            canRecord={canRecord}
            canApprove={canApprove}
            canSelfReport={canSelfReport}
            locked={awarded}
            earned={earned}
          />
        ))}
      </CardContent>
    </Card>
  )
}

function MeritBadgeSection({
  memberId,
  canRecord,
  canSelfReport,
}: {
  memberId: string
  canRecord: boolean
  canSelfReport: boolean
}) {
  const { data: advancement } = useMemberAdvancement(memberId)
  const { data: catalog = [] } = useMeritBadges()
  const createBadge = useCreateMemberMeritBadge(memberId)
  const [selected, setSelected] = useState<string>("")

  const earnedIds = useMemo(
    () => new Set((advancement?.merit_badges ?? []).map((b) => b.merit_badge_id)),
    [advancement],
  )
  const badgeName = useMemo(() => {
    const map = new Map(catalog.map((b) => [b.id, b.name]))
    return (id: string) => map.get(id) ?? "Unknown badge"
  }, [catalog])
  const available = catalog.filter((b) => !earnedIds.has(b.id) && !b.is_discontinued)

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Merit badges</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {(advancement?.merit_badges ?? []).length === 0 && (
          <p className="text-muted-foreground text-sm">No merit badge records yet.</p>
        )}
        <div className="flex flex-wrap gap-2">
          {(advancement?.merit_badges ?? []).map((record) => (
            <Badge key={record.id} variant={statusBadgeVariant(record.status)}>
              {badgeName(record.merit_badge_id)}
              {record.date_completed ? ` · ${record.date_completed}` : " · in progress"}
            </Badge>
          ))}
        </div>
        {(canRecord || canSelfReport) && (
          <div className="flex items-end gap-2">
            <div className="flex w-64 flex-col gap-1">
              <Label className="text-xs">Record a badge</Label>
              <Select value={selected} onValueChange={(value) => setSelected(value ?? "")}>
                <SelectTrigger className="h-8">
                  <SelectValue placeholder="Choose a merit badge…" />
                </SelectTrigger>
                <SelectContent>
                  {available.map((badge) => (
                    <SelectItem key={badge.id} value={badge.id}>
                      {badge.name}
                      {badge.eagle_required ? " ★" : ""}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button
              size="sm"
              disabled={!selected || createBadge.isPending}
              onClick={() => {
                createBadge.mutate({ merit_badge_id: selected, date_completed: today() })
                setSelected("")
              }}
            >
              {canRecord ? "Record" : "Report"}
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

/**
 * The full advancement view for one member: rank cards with requirement rows
 * and metric meters, plus the merit badge section. Shared between the member
 * page (`/members/[id]/advancement`) and the advancement viewer
 * (`/advancement/scouts`) — permissions drive which affordances render, and
 * the backend stays authoritative either way.
 */
export function MemberAdvancementView({ memberId }: { memberId: string }) {
  const { data: advancement, isLoading, error } = useMemberAdvancement(memberId)
  const { has } = usePermissions()
  const { data: session } = useSession()
  const { data: settings } = useTenantSettings()

  const canRecord = has("advancement:record")
  const canApprove = has("advancement:approve")
  // Self/ward reporting is only offered in scout_reported mode; the backend is
  // the authority — this only controls whether the buttons render.
  const canSelfReport =
    settings?.advancement_mode === "scout_reported" &&
    (session?.member?.id === memberId || !has("advancement:read"))

  if (error) {
    return (
      <p className="text-muted-foreground text-sm">
        Advancement is not available for this member.
      </p>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      {isLoading && <Skeleton className="h-40 w-full" />}
      {advancement?.ranks.map((view) => (
        <RankCard
          key={view.rank.id}
          memberId={memberId}
          view={view}
          canRecord={canRecord}
          canApprove={canApprove}
          canSelfReport={Boolean(canSelfReport)}
        />
      ))}
      {advancement && (
        <>
          <Separator />
          <MeritBadgeSection
            memberId={memberId}
            canRecord={canRecord}
            canSelfReport={Boolean(canSelfReport)}
          />
        </>
      )}
    </div>
  )
}
