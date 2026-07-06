"use client"

import { useRouter } from "next/navigation"
import { Lock } from "lucide-react"
import { PageHeader } from "@/components/page-header"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { useEventTypes } from "@/hooks/use-events"
import { usePermissions } from "@/hooks/use-session"
import type { EventType } from "@/types/api"

// Capability flags → short label, shown as badges on each row.
const CAPABILITY_LABELS: { key: keyof EventType; label: string }[] = [
  { key: "allow_signups", label: "Sign-ups" },
  { key: "allow_guests", label: "Guests" },
  { key: "require_permission_slip", label: "Permission slip" },
  { key: "is_online", label: "Online" },
  { key: "tracks_service_hours", label: "Service hrs" },
  { key: "tracks_camping_nights", label: "Camping" },
  { key: "tracks_mileage", label: "Mileage" },
]

export default function EventTypesPage() {
  const router = useRouter()
  const { has } = usePermissions()
  const { data: eventTypes = [], isLoading } = useEventTypes()

  const canManage = has("event:write")
  const sorted = [...eventTypes].sort((a, b) => a.name.localeCompare(b.name))

  return (
    <>
      <PageHeader title="Event Types">
        {canManage && (
          <Button size="sm" onClick={() => router.push("/events/types/new")}>
            New event type
          </Button>
        )}
      </PageHeader>

      <div className="flex-1 p-4 md:p-6">
        {isLoading ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : eventTypes.length === 0 ? (
          <div className="text-center py-12 space-y-2">
            <p className="text-sm font-medium">No event types yet.</p>
            <p className="text-sm text-muted-foreground">
              Event types classify events and control capabilities like sign-ups and activity tracking.
            </p>
            {canManage && (
              <Button size="sm" className="mt-2" onClick={() => router.push("/events/types/new")}>
                New event type →
              </Button>
            )}
          </div>
        ) : (
          <div className="rounded-md border overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/40">
                  <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    Name
                  </th>
                  <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    Capabilities
                  </th>
                  <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground w-24">
                    Status
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {sorted.map((t) => {
                  const caps = CAPABILITY_LABELS.filter((c) => t[c.key])
                  const clickable = canManage
                  return (
                    <tr
                      key={t.id}
                      onClick={clickable ? () => router.push(`/events/types/${t.id}/edit`) : undefined}
                      className={clickable ? "cursor-pointer hover:bg-muted/40 transition-colors" : ""}
                    >
                      <td className="px-4 py-3 font-medium">
                        <div className="flex items-center gap-2">
                          <span
                            className="h-3 w-3 shrink-0 rounded-full border"
                            style={{ backgroundColor: t.color ?? "transparent" }}
                            aria-hidden
                          />
                          <span>{t.name}</span>
                          {t.is_system && (
                            <Lock className="h-3.5 w-3.5 text-muted-foreground shrink-0" aria-label="System" />
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-1.5">
                          {caps.length === 0 ? (
                            <span className="text-muted-foreground">—</span>
                          ) : (
                            caps.map((c) => (
                              <Badge key={c.key} variant="outline">
                                {c.label}
                              </Badge>
                            ))
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        {t.is_active ? (
                          <span className="text-muted-foreground">Active</span>
                        ) : (
                          <Badge variant="outline" className="text-muted-foreground">
                            Inactive
                          </Badge>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  )
}
