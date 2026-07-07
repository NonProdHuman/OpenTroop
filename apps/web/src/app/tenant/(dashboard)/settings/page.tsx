"use client"

import { PageHeader } from "@/components/page-header"
import { useTenantSettings, useUpdateTenantSettings } from "@/hooks/use-tenant-settings"
import {
  useNotificationPreferences,
  useUpdateNotificationPreferences,
} from "@/hooks/use-notification-preferences"
import { usePermissions } from "@/hooks/use-session"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import type { AdvancementMode, AnnouncementEmailMode } from "@/types/api"

const MODE_DESCRIPTIONS: Record<AdvancementMode, string> = {
  disabled: "Advancement is hidden for this troop — no tracking, no navigation entry.",
  chair_entry:
    "Only advancement recorders and approvers enter progress; entries count immediately.",
  scout_reported:
    "Scouts and parents report completed requirements; the advancement chair reviews an approval queue.",
}

// digest_day follows Python's date.weekday(): 0 = Monday … 6 = Sunday.
const DAY_LABELS: Record<number, string> = {
  0: "Monday",
  1: "Tuesday",
  2: "Wednesday",
  3: "Thursday",
  4: "Friday",
  5: "Saturday",
  6: "Sunday",
}

const ANNOUNCEMENT_MODE_LABELS: Record<AnnouncementEmailMode, string> = {
  every: "Every announcement",
  digest: "Weekly newsletter only",
  none: "No announcement emails",
}

const ANNOUNCEMENT_MODE_DESCRIPTIONS: Record<AnnouncementEmailMode, string> = {
  every: "Email me each announcement as it's sent.",
  digest: "Hold announcement emails and send them together in the weekly newsletter.",
  none: "Don't email me announcements. (You'll still see them in the app and get event emails.)",
}

export default function SettingsPage() {
  const { data: settings, isLoading } = useTenantSettings()
  const update = useUpdateTenantSettings()
  const { has } = usePermissions()
  const canManage = has("role:manage")

  const { data: prefs, isLoading: prefsLoading } = useNotificationPreferences()
  const updatePrefs = useUpdateNotificationPreferences()

  return (
    <>
      <PageHeader title="Settings" />
      <div className="flex flex-1 flex-col gap-4 p-4">
        {canManage && (
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Advancement</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-2">
              {isLoading && <Skeleton className="h-9 w-72" />}
              {settings && (
                <>
                  <Label className="text-xs" htmlFor="advancement-mode">
                    Workflow mode
                  </Label>
                  <Select
                    value={settings.advancement_mode}
                    onValueChange={(value) =>
                      update.mutate({ advancement_mode: value as AdvancementMode })
                    }
                  >
                    <SelectTrigger id="advancement-mode" className="w-72">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="chair_entry">Chair entry</SelectItem>
                      <SelectItem value="scout_reported">Scout reported + approval</SelectItem>
                      <SelectItem value="disabled">Disabled</SelectItem>
                    </SelectContent>
                  </Select>
                  <p className="text-muted-foreground text-sm">
                    {MODE_DESCRIPTIONS[settings.advancement_mode]}
                  </p>
                </>
              )}
            </CardContent>
          </Card>
        )}

        {canManage && (
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Newsletter schedule</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-2">
              {isLoading && <Skeleton className="h-9 w-72" />}
              {settings && (
                <>
                  <p className="text-muted-foreground text-sm">
                    When the weekly digest of held announcements goes out (UTC).
                  </p>
                  <div className="flex flex-wrap gap-4">
                    <div className="flex flex-col gap-1">
                      <Label className="text-xs" htmlFor="digest-day">
                        Day
                      </Label>
                      <Select
                        value={String(settings.digest_day)}
                        onValueChange={(value) => update.mutate({ digest_day: Number(value) })}
                      >
                        <SelectTrigger id="digest-day" className="w-40">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {Object.entries(DAY_LABELS).map(([value, label]) => (
                            <SelectItem key={value} value={value}>
                              {label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="flex flex-col gap-1">
                      <Label className="text-xs" htmlFor="digest-hour">
                        Hour (UTC)
                      </Label>
                      <Select
                        value={String(settings.digest_hour_utc)}
                        onValueChange={(value) =>
                          update.mutate({ digest_hour_utc: Number(value) })
                        }
                      >
                        <SelectTrigger id="digest-hour" className="w-40">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {Array.from({ length: 24 }, (_, h) => (
                            <SelectItem key={h} value={String(h)}>
                              {String(h).padStart(2, "0")}:00
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        )}

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Notification preferences</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-2">
            {prefsLoading && <Skeleton className="h-9 w-72" />}
            {prefs && (
              <>
                <Label className="text-xs" htmlFor="announcement-mode">
                  Announcement emails
                </Label>
                <Select
                  value={prefs.announcement_email_mode}
                  onValueChange={(value) =>
                    updatePrefs.mutate({
                      announcement_email_mode: value as AnnouncementEmailMode,
                    })
                  }
                >
                  <SelectTrigger id="announcement-mode" className="w-72">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {(Object.keys(ANNOUNCEMENT_MODE_LABELS) as AnnouncementEmailMode[]).map(
                      (mode) => (
                        <SelectItem key={mode} value={mode}>
                          {ANNOUNCEMENT_MODE_LABELS[mode]}
                        </SelectItem>
                      ),
                    )}
                  </SelectContent>
                </Select>
                <p className="text-muted-foreground text-sm">
                  {ANNOUNCEMENT_MODE_DESCRIPTIONS[prefs.announcement_email_mode]}
                </p>
                {prefs.email_bounced && (
                  <p className="text-destructive text-sm">
                    We couldn&apos;t deliver to your email address, so announcement emails are
                    paused. Update your email to resume them.
                  </p>
                )}
                {prefs.email_opt_out && (
                  <p className="text-muted-foreground text-sm">
                    You&apos;re globally opted out of all troop email.
                  </p>
                )}
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </>
  )
}
