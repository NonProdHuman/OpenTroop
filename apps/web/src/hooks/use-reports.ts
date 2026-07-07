"use client"

import { useCallback } from "react"
import { useQuery } from "@tanstack/react-query"
import { queryKeys } from "@/lib/query-keys"
import { useApi } from "@/lib/api"
import { useActiveTenant } from "@/lib/tenant-context"
import type { ReportCatalogEntry, ReportData } from "@/types/api"

/** Build a query string from report params, dropping empty values. */
function toQuery(params: Record<string, string>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== "") search.set(key, value)
  }
  const qs = search.toString()
  return qs ? `?${qs}` : ""
}

/** The report catalog with a per-report `runnable` flag for the caller. */
export function useReportCatalog() {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: queryKeys.reportCatalog(activeTenantId),
    queryFn: () => request<ReportCatalogEntry[]>("/reports"),
    enabled: Boolean(activeTenantId),
  })
}

/** Rendered rows + columns for one report (`format=json`). */
export function useReport(key: string | null, params: Record<string, string>) {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: queryKeys.report(activeTenantId, key ?? "", params),
    queryFn: () => request<ReportData>(`/reports/${key}${toQuery({ ...params, format: "json" })}`),
    enabled: key !== null && Boolean(activeTenantId),
  })
}

/** Download a report as a CSV attachment (streamed by the backend). */
export function useReportCsvDownload() {
  const { requestBlob } = useApi()
  return useCallback(
    async (key: string, params: Record<string, string>) => {
      const blob = await requestBlob(`/reports/${key}${toQuery({ ...params, format: "csv" })}`)
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement("a")
      anchor.href = url
      anchor.download = `${key}-report.csv`
      document.body.appendChild(anchor)
      anchor.click()
      anchor.remove()
      URL.revokeObjectURL(url)
    },
    [requestBlob],
  )
}
