import { useCallback, useState } from "react"
import { apiBaseUrl } from "@/lib/env"
import { useActiveTenant } from "@/lib/tenant-context"
import { useSyncContext } from "@/lib/sync-context"
import type { CalendarSubscription } from "@/lib/types"

/**
 * Personal iCal subscription (GH-114): the phone is the easy place to add a
 * calendar. The raw token is shown once at mint/rotate time; we build the full
 * webcal URL for the OS calendar picker.
 */

function feedUrl(slug: string, feedPath: string | null): string | null {
  if (!feedPath) return null
  const base = apiBaseUrl(slug)
  // webcal:// makes iOS/Android offer to subscribe instead of download.
  return base.replace(/^https?:\/\//, "webcal://") + feedPath
}

export function useCalendarSubscription() {
  const { http } = useSyncContext()
  const { activeTenant } = useActiveTenant()
  const [url, setUrl] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const mint = useCallback(
    async (method: "POST" | "DELETE") => {
      if (!http || !activeTenant) return
      setBusy(true)
      setError(null)
      try {
        const response = await http("/calendar/subscription", { method })
        if (response.status >= 400) throw new Error(`HTTP ${response.status}`)
        const body = response.body as CalendarSubscription
        const built = feedUrl(activeTenant.tenant_slug, body.feed_path ?? null)
        setUrl(built)
        if (!built && body.active) {
          // Already subscribed (POST won't re-reveal the token) — rotate to see one.
          setError("Already subscribed. Tap “Get a fresh link” to reveal a new URL.")
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Could not create the calendar link.")
      } finally {
        setBusy(false)
      }
    },
    [http, activeTenant],
  )

  return {
    url,
    busy,
    error,
    /** Mint (or reveal a fresh) subscription URL. */
    create: () => mint("POST"),
    /** Rotate — old URLs stop working, returns a new one. */
    rotate: () => mint("DELETE"),
  }
}
