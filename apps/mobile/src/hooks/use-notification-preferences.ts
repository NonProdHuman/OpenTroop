import { useCallback, useEffect, useState } from "react"
import { useSyncContext } from "@/lib/sync-context"
import { useActiveTenant } from "@/lib/tenant-context"
import type { AnnouncementEmailMode, NotificationPreferences } from "@/lib/types"

/**
 * The signed-in member's announcement email preference (GH-218). Loads once and
 * exposes a ``cycle`` that advances every → digest → none → every, PATCHing the
 * self-service endpoint. Inbox/push are unaffected — this only gates email.
 */

const ORDER: AnnouncementEmailMode[] = ["every", "digest", "none"]

const PATH = "/members/me/notification-preferences"

export function useNotificationPreferences() {
  const { http } = useSyncContext()
  const { activeTenant } = useActiveTenant()
  const [mode, setMode] = useState<AnnouncementEmailMode | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    if (!http || !activeTenant) return
    void (async () => {
      try {
        const response = await http(PATH, { method: "GET" })
        if (response.status >= 400) throw new Error(`HTTP ${response.status}`)
        if (!cancelled) {
          setMode((response.body as NotificationPreferences).announcement_email_mode)
        }
      } catch {
        if (!cancelled) setError("Could not load notification preferences.")
      }
    })()
    return () => {
      cancelled = true
    }
  }, [http, activeTenant])

  const cycle = useCallback(async () => {
    if (!http || mode === null || busy) return
    const next = ORDER[(ORDER.indexOf(mode) + 1) % ORDER.length]
    setBusy(true)
    setError(null)
    try {
      const response = await http(PATH, {
        method: "PATCH",
        body: { announcement_email_mode: next },
      })
      if (response.status >= 400) throw new Error(`HTTP ${response.status}`)
      setMode((response.body as NotificationPreferences).announcement_email_mode)
    } catch {
      setError("Could not update notification preferences.")
    } finally {
      setBusy(false)
    }
  }, [http, mode, busy])

  return { mode, busy, error, cycle }
}
