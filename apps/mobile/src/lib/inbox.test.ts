import { describe, expect, it } from "vitest"
import { composeInbox } from "./inbox"
import type { Message, MessageRecipient } from "@/lib/types"

const message = (id: string, sent: string, extra: Partial<Message> = {}): Message =>
  ({ id, subject: `S-${id}`, body: `B-${id}`, sent_at: sent, updated_at: sent, ...extra }) as Message

const recipient = (id: string, messageId: string, readAt: string | null): MessageRecipient =>
  ({ id, message_id: messageId, read_at: readAt } as MessageRecipient)

describe("composeInbox", () => {
  it("joins, sorts newest-first, and counts unread", () => {
    const { items, unreadCount } = composeInbox(
      [recipient("r1", "m1", null), recipient("r2", "m2", "2026-07-05T00:00:00Z")],
      [message("m1", "2026-07-01T00:00:00Z"), message("m2", "2026-07-04T00:00:00Z")],
    )
    expect(items.map((i) => i.messageId)).toEqual(["m2", "m1"])
    expect(items[1]).toMatchObject({ subject: "S-m1", body: "B-m1", readAt: null })
    expect(unreadCount).toBe(1)
  })

  it("drops recipients whose message hasn't synced yet", () => {
    const { items } = composeInbox([recipient("r1", "missing", null)], [])
    expect(items).toEqual([])
  })
})
