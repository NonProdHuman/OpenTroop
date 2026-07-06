"use client"

import { PageHeader } from "@/components/page-header"
import { useTenantSettings, useUpdateTenantSettings } from "@/hooks/use-tenant-settings"
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
import type { AdvancementMode } from "@/types/api"

const MODE_DESCRIPTIONS: Record<AdvancementMode, string> = {
  disabled: "Advancement is hidden for this troop — no tracking, no navigation entry.",
  chair_entry:
    "Only advancement recorders and approvers enter progress; entries count immediately.",
  scout_reported:
    "Scouts and parents report completed requirements; the advancement chair reviews an approval queue.",
}

export default function SettingsPage() {
  const { data: settings, isLoading } = useTenantSettings()
  const update = useUpdateTenantSettings()

  return (
    <>
      <PageHeader title="Settings" />
      <div className="flex flex-1 flex-col gap-4 p-4">
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
      </div>
    </>
  )
}
