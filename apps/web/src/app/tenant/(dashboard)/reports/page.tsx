"use client"

import Link from "next/link"
import { BarChart3 } from "lucide-react"
import { PageHeader } from "@/components/page-header"
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { useReportCatalog } from "@/hooks/use-reports"

export default function ReportsCatalogPage() {
  const { data: reports = [], isLoading } = useReportCatalog()
  // Only reports the caller may actually run are offered.
  const runnable = reports.filter((r) => r.runnable)

  return (
    <>
      <PageHeader title="Reports" />
      <div className="flex-1 space-y-4 p-4 md:p-6">
        {isLoading ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-28 w-full rounded-lg" />
            ))}
          </div>
        ) : runnable.length === 0 ? (
          <p className="text-sm text-muted-foreground">No reports are available for your role.</p>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {runnable.map((report) => (
              <Link key={report.key} href={`/reports/${report.key}`} className="block">
                <Card className="h-full transition-colors hover:border-primary/50">
                  <CardHeader>
                    <div className="flex items-center gap-2">
                      <BarChart3 className="h-4 w-4 text-muted-foreground" />
                      <CardTitle className="text-base">{report.title}</CardTitle>
                    </div>
                    <CardDescription>{report.description}</CardDescription>
                  </CardHeader>
                </Card>
              </Link>
            ))}
          </div>
        )}
      </div>
    </>
  )
}
