import { useCallback, useMemo } from "react"
import { listRows } from "@/data/mirror"
import { useSyncContext } from "@/lib/sync-context"
import { composeInbox, type InboxItem } from "@/lib/inbox"
import type { Message, MessageRecipient } from "@/lib/types"

export type { InboxItem }

/**
 * The member inbox on the offline mirror (GH-146): join the caller-scoped
 * inbox_recipients (read state) with inbox_messages (content). Reads are
 * always local; marking read writes the mirror optimistically and best-effort
 * POSTs to the server (the next pull confirms it).
 */

export function useInbox(): { items: InboxItem[]; unreadCount: number } {
  const { db, version } = useSyncContext()
  return useMemo(() => {
    if (!db) return { items: [], unreadCount: 0 }
    void version
    return composeInbox(
      listRows<MessageRecipient>(db, "inbox_recipients"),
      listRows<Message>(db, "inbox_messages"),
    )
  }, [db, version])
}

export function useMarkInboxRead(): (recipientId: string) => void {
  const { db, http, bump } = useSyncContext()
  return useCallback(
    (recipientId: string) => {
      if (!db) return
      // Optimistic local write — instant unread-badge update, persists offline.
      const row = db.get<{ data: string }>(
        "SELECT data FROM inbox_recipients WHERE id = ?",
        [recipientId],
      )
      if (row) {
        const parsed = JSON.parse(row.data) as MessageRecipient
        if (parsed.read_at === null) {
          parsed.read_at = new Date().toISOString()
          db.run("UPDATE inbox_recipients SET data = ? WHERE id = ?", [
            JSON.stringify(parsed),
            recipientId,
          ])
          bump()
        }
      }
      // Best-effort server sync; the next pull reconciles either way.
      if (http) {
        void http(`/messages/inbox/${recipientId}/read`, { method: "POST" }).catch(() => undefined)
      }
    },
    [db, http, bump],
  )
}
