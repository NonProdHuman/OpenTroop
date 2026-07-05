/** Pure inbox composition (GH-146) — unit-tested in Node, no RN/DB imports. */

import type { Message, MessageRecipient } from "@/lib/types"

export type InboxItem = {
  recipientId: string
  messageId: string
  subject: string
  body: string
  sentAt: string
  readAt: string | null
}

/**
 * Join the caller's inbox_recipients (read state) with inbox_messages
 * (content), newest first. A recipient whose message hasn't synced yet is
 * dropped (it heals on the next pull round — LEFT-JOIN semantics, §C1).
 */
export function composeInbox(
  recipients: MessageRecipient[],
  messages: Message[],
): { items: InboxItem[]; unreadCount: number } {
  const byId = new Map(messages.map((m) => [m.id, m]))
  const items = recipients
    .map((recipient) => {
      const message = byId.get(recipient.message_id)
      if (!message) return null
      return {
        recipientId: recipient.id,
        messageId: message.id,
        subject: message.subject,
        body: message.body,
        sentAt: message.sent_at ?? message.updated_at ?? "",
        readAt: recipient.read_at,
      }
    })
    .filter((item): item is InboxItem => item !== null)
    .sort((a, b) => b.sentAt.localeCompare(a.sentAt))
  return { items, unreadCount: items.filter((i) => i.readAt === null).length }
}
