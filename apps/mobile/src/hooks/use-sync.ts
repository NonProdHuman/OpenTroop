import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { AppState } from "react-native"
import NetInfo from "@react-native-community/netinfo"
import { useAuth } from "@clerk/clerk-expo"
import { apiBaseUrl, usesTenantHeader } from "@/lib/env"
import { useActiveTenant } from "@/lib/tenant-context"
import { openTenantDatabase } from "@/data/expo-db"
import {
  discardCommand,
  listCommands,
  type HttpClient,
  type PendingCommand,
} from "@/data/commands"
import { syncNow, type SyncOutcome } from "@/data/engine"

/**
 * Binds the GH-153 sync engine to the app: opens the active tenant's database
 * and runs a sync round on tenant switch, app foreground, connectivity
 * regain, and on demand (pull-to-refresh). Reads stay local — this hook is
 * the only network toucher besides the M3 online-read hooks it will replace.
 */
export function useSync() {
  const { getToken } = useAuth()
  const { activeTenant } = useActiveTenant()
  const [isSyncing, setIsSyncing] = useState(false)
  const [lastOutcome, setLastOutcome] = useState<SyncOutcome | null>(null)
  const [failedCommands, setFailedCommands] = useState<PendingCommand[]>([])
  const inFlight = useRef(false)

  const db = useMemo(
    () => (activeTenant ? openTenantDatabase(activeTenant.tenant_id) : null),
    [activeTenant],
  )

  const http = useMemo<HttpClient | null>(() => {
    if (!activeTenant) return null
    return async (path, init) => {
      const token = await getToken()
      const headers: Record<string, string> = { "Content-Type": "application/json" }
      if (token) headers.Authorization = `Bearer ${token}`
      if (usesTenantHeader()) headers["X-Tenant-ID"] = activeTenant.tenant_id
      const response = await fetch(`${apiBaseUrl(activeTenant.tenant_slug)}${path}`, {
        method: init.method,
        headers,
        body: init.body === undefined ? undefined : JSON.stringify(init.body),
      })
      let body: unknown = null
      try {
        body = await response.json()
      } catch {
        // 204s and empty error bodies are fine
      }
      return { status: response.status, body }
    }
  }, [activeTenant, getToken])

  const refreshFailed = useCallback(() => {
    if (db) setFailedCommands(listCommands(db, "failed"))
  }, [db])

  const sync = useCallback(
    async (opts: { full?: boolean } = {}) => {
      if (!db || !http || inFlight.current) return
      inFlight.current = true
      setIsSyncing(true)
      try {
        const outcome = await syncNow(db, http, opts)
        setLastOutcome(outcome)
        refreshFailed()
      } finally {
        inFlight.current = false
        setIsSyncing(false)
      }
    },
    [db, http, refreshFailed],
  )

  const discard = useCallback(
    (commandId: string) => {
      if (!db) return
      discardCommand(db, commandId)
      refreshFailed()
    },
    [db, refreshFailed],
  )

  // Tenant switch / first mount. sync() refreshes the failed list when done
  // (even fully offline the drain resolves), so no synchronous setState here.
  useEffect(() => {
    void sync()
  }, [sync])

  // Connectivity regain drains the outbox (GH-153 §C3).
  useEffect(() => {
    const unsubscribe = NetInfo.addEventListener((state) => {
      if (state.isConnected) void sync()
    })
    return unsubscribe
  }, [sync])

  // App foreground.
  useEffect(() => {
    const sub = AppState.addEventListener("change", (state) => {
      if (state === "active") void sync()
    })
    return () => sub.remove()
  }, [sync])

  return { db, sync, isSyncing, lastOutcome, failedCommands, discard }
}
