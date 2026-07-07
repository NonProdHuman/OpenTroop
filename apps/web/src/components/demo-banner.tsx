"use client"

import { useSyncExternalStore } from "react"
import { isDemoHost } from "@/lib/domains"

const noopSubscribe = () => () => {}

// Site-wide notice shown only on the public demo host (GH-246). The demo troop is
// read-only for anonymous visitors; writes 403 on the backend and the permission-
// driven UI already hides most write affordances. `isDemoHost()` is client-only, so
// useSyncExternalStore reads `false` on the server (getServerSnapshot) and the real
// value on the client — the hydration-safe way to branch on host without a mismatch.
export function DemoBanner() {
  const show = useSyncExternalStore(
    noopSubscribe,
    () => isDemoHost(),
    () => false,
  )

  if (!show) return null

  return (
    <div
      data-testid="demo-banner"
      role="status"
      className="flex flex-wrap items-center justify-center gap-x-2 bg-amber-100 px-4 py-2 text-center text-sm text-amber-900 dark:bg-amber-950 dark:text-amber-100"
    >
      <span>You&rsquo;re viewing a read-only demo troop &mdash; data resets are fake.</span>
      <a
        href="mailto:hello@opentroop.dev?subject=OpenTroop%20demo%20edit%20access"
        className="font-medium underline underline-offset-2"
      >
        Request edit access
      </a>
    </div>
  )
}
