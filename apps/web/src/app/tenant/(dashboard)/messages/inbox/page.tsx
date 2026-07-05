"use client"

import { useState } from "react"
import { useInbox, useMarkInboxRead } from "@/hooks/use-messages"
import { PageHeader } from "@/components/page-header"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import type { InboxEntry } from "@/types/api"

function formatSent(iso: string | null): string {
  if (!iso) return ""
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  })
}

function InboxRow({ entry }: { entry: InboxEntry }) {
  const [open, setOpen] = useState(false)
  const markRead = useMarkInboxRead()
  const unread = entry.read_at === null

  const toggle = () => {
    setOpen((o) => !o)
    if (unread) markRead.mutate(entry.recipient_id)
  }

  return (
    <button
      type="button"
      onClick={toggle}
      className="hover:bg-muted/40 flex w-full flex-col items-start gap-1 px-4 py-3 text-left"
    >
      <div className="flex w-full items-center justify-between gap-2">
        <span className={`text-sm ${unread ? "font-semibold" : "font-medium"}`}>
          {entry.subject}
        </span>
        <span className="flex items-center gap-2">
          {unread && <Badge>New</Badge>}
          <span className="text-muted-foreground text-xs">{formatSent(entry.sent_at)}</span>
        </span>
      </div>
      <p
        className={`text-muted-foreground text-sm ${open ? "whitespace-pre-wrap" : "line-clamp-1"}`}
      >
        {entry.body}
      </p>
    </button>
  )
}

export default function InboxPage() {
  const { data, isLoading } = useInbox()

  return (
    <>
      <PageHeader title="Inbox">
        {data && data.unread_count > 0 && <Badge>{data.unread_count} unread</Badge>}
      </PageHeader>
      <div className="flex flex-1 flex-col p-4">
        {isLoading && <Skeleton className="h-40 w-full" />}
        {data && data.items.length === 0 && (
          <p className="text-muted-foreground text-sm">
            No messages yet. Troop announcements will appear here.
          </p>
        )}
        {data && data.items.length > 0 && (
          <Card>
            <CardContent className="divide-y p-0">
              {data.items.map((entry) => (
                <InboxRow key={entry.recipient_id} entry={entry} />
              ))}
            </CardContent>
          </Card>
        )}
      </div>
    </>
  )
}
