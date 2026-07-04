import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react"
import { AppState } from "react-native"
import NetInfo from "@react-native-community/netinfo"
import { useAuth } from "@clerk/clerk-expo"
import { apiBaseUrl, usesTenantHeader } from "@/lib/env"
import { useActiveTenant } from "@/lib/tenant-context"
import { openTenantDatabase } from "@/data/expo-db"
import {
  discardCommand,
  enqueueCommand,
  listCommands,
  type CommandKind,
  type CommandPayload,
  type HttpClient,
  type PendingCommand,
} from "@/data/commands"
import { syncNow, type SyncOutcome } from "@/data/engine"
import { setMeta } from "@/data/schema"
import type { SqlDatabase } from "@/data/db"

/**
 * One sync engine per app (GH-153): a single tenant database handle, a single
 * drain-then-pull loop, and a version counter that bumps whenever the mirror
 * or the outbox changes so mirror-backed reads recompute. Screens consume
 * this through `useSyncContext` / the hooks in `use-mirror.ts`.
 */

type SyncContextValue = {
  db: SqlDatabase | null
  /** Monotonic counter: bumps on sync completion and on local enqueue/discard. */
  version: number
  sync: (opts?: { full?: boolean }) => Promise<void>
  isSyncing: boolean
  lastOutcome: SyncOutcome | null
  failedCommands: PendingCommand[]
  enqueue: (kind: CommandKind, payload: CommandPayload) => void
  discard: (commandId: string) => void
}

const SyncContext = createContext<SyncContextValue | null>(null)

export function SyncProvider({ children }: { children: ReactNode }) {
  const { getToken } = useAuth()
  const { activeTenant } = useActiveTenant()
  const [version, setVersion] = useState(0)
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

  const sync = useCallback(
    async (opts: { full?: boolean } = {}) => {
      if (!db || !http || inFlight.current) return
      inFlight.current = true
      setIsSyncing(true)
      try {
        const outcome = await syncNow(db, http, opts)
        if (outcome.pulled) {
          // Permission-set snapshot for offline UI affordances only (§C1);
          // the server re-checks everything at replay time.
          try {
            const session = await http("/auth/session", { method: "GET" })
            if (session.status === 200) {
              setMeta(db, "session_snapshot", JSON.stringify(session.body))
            }
          } catch {
            // snapshot refresh is best-effort
          }
        }
        setLastOutcome(outcome)
        setFailedCommands(listCommands(db, "failed"))
        setVersion((v) => v + 1)
      } finally {
        inFlight.current = false
        setIsSyncing(false)
      }
    },
    [db, http],
  )

  const enqueue = useCallback(
    (kind: CommandKind, payload: CommandPayload) => {
      if (!db) return
      enqueueCommand(db, kind, payload)
      setVersion((v) => v + 1)
      void sync() // opportunistic immediate replay when online
    },
    [db, sync],
  )

  const discard = useCallback(
    (commandId: string) => {
      if (!db) return
      discardCommand(db, commandId)
      setFailedCommands(listCommands(db, "failed"))
      setVersion((v) => v + 1)
    },
    [db],
  )

  // Tenant switch / first mount.
  useEffect(() => {
    void sync()
  }, [sync])

  // Connectivity regain drains the outbox (§C3).
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

  const value = useMemo(
    () => ({ db, version, sync, isSyncing, lastOutcome, failedCommands, enqueue, discard }),
    [db, version, sync, isSyncing, lastOutcome, failedCommands, enqueue, discard],
  )
  return <SyncContext.Provider value={value}>{children}</SyncContext.Provider>
}

export function useSyncContext(): SyncContextValue {
  const ctx = useContext(SyncContext)
  if (!ctx) throw new Error("useSyncContext must be used within SyncProvider")
  return ctx
}
