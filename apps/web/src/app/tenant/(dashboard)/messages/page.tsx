"use client"

import Link from "next/link"
import { useMessages } from "@/hooks/use-messages"
import { PageHeader } from "@/components/page-header"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import type { Message } from "@/types/api"

function statusVariant(status: Message["status"]): "default" | "secondary" | "outline" {
  if (status === "sent") return "default"
  if (status === "scheduled") return "secondary"
  return "outline"
}

function formatWhen(message: Message): string {
  const iso = message.sent_at ?? message.scheduled_at ?? message.created_at
  return new Date(iso).toLocaleDateString(undefined, { dateStyle: "medium" })
}

export default function AnnouncementsPage() {
  const { data: messages, isLoading } = useMessages()

  return (
    <>
      <PageHeader title="Announcements">
        <Button size="sm" render={<Link href="/messages/new" />} nativeButton={false}>
          New announcement
        </Button>
      </PageHeader>
      <div className="flex flex-1 flex-col p-4">
        {isLoading && <Skeleton className="h-40 w-full" />}
        {messages && messages.length === 0 && (
          <p className="text-muted-foreground text-sm">
            No announcements yet. Send one to reach your troop by email, push, and in-app.
          </p>
        )}
        {messages && messages.length > 0 && (
          <Card>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Subject</TableHead>
                    <TableHead className="w-32">Date</TableHead>
                    <TableHead className="w-28">Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {messages.map((message) => (
                    <TableRow key={message.id}>
                      <TableCell>
                        <Link className="font-medium hover:underline" href={`/messages/${message.id}`}>
                          {message.subject}
                        </Link>
                      </TableCell>
                      <TableCell className="text-muted-foreground text-sm">
                        {formatWhen(message)}
                      </TableCell>
                      <TableCell>
                        <Badge variant={statusVariant(message.status)}>{message.status}</Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        )}
      </div>
    </>
  )
}
