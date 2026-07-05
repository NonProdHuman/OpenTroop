import { useEffect, useState, type ReactNode } from "react"
import * as SecureStore from "expo-secure-store"
import { useAuth } from "@clerk/clerk-expo"
import { LoadingScreen } from "@/components/loading-screen"
import { wipeAllLocalData } from "./local-wipe"

const LAST_USER_KEY = "opentroop.last-user-id"

/**
 * GH-153 §C5: the device's local data belongs to an identity, not the device.
 * Sign-out wipes eagerly, but if that path is skipped (force-quit mid
 * sign-out), a *different* user signing in must not inherit the previous
 * user's mirrored tenant databases. This gate runs before anything opens a
 * database: a changed Clerk user id wipes all local tenant data first.
 */
export function IdentityGate({ children }: { children: ReactNode }) {
  const { isLoaded, userId } = useAuth()
  const [checked, setChecked] = useState(false)

  useEffect(() => {
    if (!isLoaded) return
    let cancelled = false
    void (async () => {
      try {
        const lastUserId = await SecureStore.getItemAsync(LAST_USER_KEY)
        if (userId && lastUserId && lastUserId !== userId) {
          await wipeAllLocalData()
        }
        if (userId && userId !== lastUserId) {
          await SecureStore.setItemAsync(LAST_USER_KEY, userId)
        }
      } finally {
        if (!cancelled) setChecked(true)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [isLoaded, userId])

  if (!isLoaded || !checked) return <LoadingScreen />
  return <>{children}</>
}
