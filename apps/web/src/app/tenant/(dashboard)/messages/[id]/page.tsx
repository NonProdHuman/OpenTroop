"use client"

import { useParams } from "next/navigation"
import { useMessage } from "@/hooks/use-messages"
import { PageHeader } from "@/components/page-header"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex flex-col">
      <span className="text-2xl font-semibold">{value}</span>
      <span className="text-muted-foreground text-xs">{label}</span>
    </div>
  )
}

export default function MessageDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { data, isLoading } = useMessage(id)

  return (
    <>
      <PageHeader title={data?.message.subject ?? "Announcement"}>
        {data && <Badge>{data.message.status}</Badge>}
      </PageHeader>
      <div className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-4 p-4">
        {isLoading && <Skeleton className="h-40 w-full" />}
        {data && (
          <>
            <Card>
              <CardContent className="py-4">
                <p className="text-sm whitespace-pre-wrap">{data.message.body}</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Delivery</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-wrap gap-x-8 gap-y-4">
                <Stat label="Recipients" value={data.stats.total} />
                <Stat label="Email sent" value={data.stats.email_sent} />
                <Stat label="Email pending" value={data.stats.email_pending} />
                <Stat label="Email failed" value={data.stats.email_failed} />
                <Stat label="Skipped (opt-out/bounce)" value={data.stats.email_skipped} />
                <Stat label="Push sent" value={data.stats.push_sent} />
                <Stat label="Read" value={data.stats.read} />
              </CardContent>
            </Card>
          </>
        )}
      </div>
    </>
  )
}
