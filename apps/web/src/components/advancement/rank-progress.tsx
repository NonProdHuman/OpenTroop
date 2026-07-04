import { Badge } from "@/components/ui/badge"
import type { CompletionStatus, MemberRankView, MetricProgress } from "@/types/api"

/** Human label for a metric kind — mirrors MetricKind on the backend. */
const METRIC_LABELS: Record<string, string> = {
  camping_nights: "Camping nights",
  service_hours: "Service hours",
  conservation_hours: "Conservation hours",
  hiking_miles: "Hiking miles",
  activity_count: "Activities",
  tenure_months: "Months in rank",
  por_months: "Months in a position of responsibility",
  merit_badge_count: "Merit badges",
  merit_badge_count_eagle_required: "Eagle-required merit badges",
}

const WINDOW_LABELS: Record<string, string> = {
  any: "",
  since_joining: "since joining",
  since_rank: "since last rank",
}

export function metricLabel(metric: MetricProgress): string {
  const kind = METRIC_LABELS[metric.kind] ?? metric.kind
  const window = WINDOW_LABELS[metric.window] ?? metric.window
  return window ? `${kind} (${window})` : kind
}

export function statusBadgeVariant(
  status: CompletionStatus,
): "default" | "secondary" | "destructive" | "outline" {
  switch (status) {
    case "approved":
      return "default"
    case "reported":
      return "secondary"
    case "rejected":
      return "destructive"
  }
}

/** Counts of complete vs. total top-level requirements for a rank card header. */
export function rankSummary(view: MemberRankView): { complete: number; total: number } {
  const topLevel = view.requirements.filter((r) => r.requirement.parent_id === null)
  return {
    complete: topLevel.filter((r) => r.is_complete).length,
    total: topLevel.length,
  }
}

export function MetricMeter({ metric }: { metric: MetricProgress }) {
  // value === null ⇒ the window anchor is unavailable (e.g. the previous rank's
  // board of review isn't recorded yet) — show why instead of a zero bar.
  if (metric.value === null) {
    return (
      <div className="text-muted-foreground flex items-center gap-2 text-xs">
        <span>{metricLabel(metric)}</span>
        <Badge variant="outline">awaiting previous rank date</Badge>
      </div>
    )
  }
  const fraction = Math.min(1, metric.value / metric.threshold)
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="text-muted-foreground w-64 shrink-0 truncate">{metricLabel(metric)}</span>
      <div className="bg-muted h-2 w-40 overflow-hidden rounded-full">
        <div
          className={`h-full rounded-full ${metric.met ? "bg-emerald-500" : "bg-primary"}`}
          style={{ width: `${Math.round(fraction * 100)}%` }}
        />
      </div>
      <span className="text-muted-foreground tabular-nums">
        {Number(metric.value.toFixed(1))} / {metric.threshold}
      </span>
    </div>
  )
}
