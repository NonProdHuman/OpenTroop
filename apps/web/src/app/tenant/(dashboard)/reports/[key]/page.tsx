"use client"

import { use, useMemo, useState } from "react"
import Link from "next/link"
import { ArrowLeft, Download, Printer } from "lucide-react"
import type { ColumnDef } from "@tanstack/react-table"
import { PageHeader } from "@/components/page-header"
import { DataTable, sortableHeader } from "@/components/data-table"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useReport, useReportCatalog, useReportCsvDownload } from "@/hooks/use-reports"
import { useGroups } from "@/hooks/use-groups"
import { useMemberships } from "@/hooks/use-memberships"
import { useActiveTenant } from "@/lib/tenant-context"
import type { ReportParamSchema, ReportValue } from "@/types/api"

type ReportRow = Record<string, ReportValue>

const ANY_GROUP = "__any__"

function initialParams(params: ReportParamSchema[]): Record<string, string> {
  const state: Record<string, string> = {}
  for (const p of params) {
    state[p.name] = p.default == null ? "" : String(p.default)
  }
  return state
}

function renderCell(value: ReportValue) {
  if (typeof value === "boolean") return value ? "Yes" : "No"
  if (value === null || value === "") return "—"
  return String(value)
}

export default function ReportPage({ params }: { params: Promise<{ key: string }> }) {
  const { key } = use(params)
  const { data: catalog = [] } = useReportCatalog()
  const entry = catalog.find((r) => r.key === key)

  const [paramState, setParamState] = useState<Record<string, string>>({})
  // Seed defaults once the catalog (and thus the param schema) has loaded.
  const [seeded, setSeeded] = useState(false)
  if (entry && !seeded) {
    setParamState(initialParams(entry.params))
    setSeeded(true)
  }

  const { data: report, isLoading, isError } = useReport(entry ? key : null, paramState)
  const download = useReportCsvDownload()
  const { data: groups = [] } = useGroups()
  const { data: memberships = [] } = useMemberships()
  const { activeTenantId } = useActiveTenant()
  const troopName = memberships.find((m) => m.tenant_id === activeTenantId)?.tenant_name ?? "Troop"

  const columns: ColumnDef<ReportRow>[] = useMemo(
    () =>
      (report?.columns ?? []).map((col) => ({
        accessorKey: col.key,
        header: sortableHeader<ReportRow>(col.label),
        cell: ({ getValue }) => renderCell(getValue() as ReportValue),
      })),
    [report?.columns],
  )

  function setParam(name: string, value: string) {
    setParamState((prev) => ({ ...prev, [name]: value }))
  }

  if (!entry) {
    return (
      <>
        <PageHeader title="Reports" />
        <div className="flex-1 p-4 md:p-6">
          <p className="text-sm text-muted-foreground">
            This report is unavailable.{" "}
            <Link href="/reports" className="underline">
              Back to reports
            </Link>
          </p>
        </div>
      </>
    )
  }

  return (
    <>
      <PageHeader title={entry.title}>
        <Button variant="ghost" size="sm" render={<Link href="/reports" />}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          All reports
        </Button>
      </PageHeader>

      <div className="flex-1 space-y-4 p-4 md:p-6">
        {/* Parameter controls — hidden when printing. */}
        <div className="report-no-print flex flex-wrap items-end gap-4">
          {entry.params.map((param) => (
            <div key={param.name} className="space-y-1.5">
              <Label htmlFor={`param-${param.name}`}>{param.label}</Label>
              {param.type === "enum" ? (
                <Select
                  value={paramState[param.name] ?? ""}
                  onValueChange={(v) => setParam(param.name, v ?? "")}
                >
                  <SelectTrigger id={`param-${param.name}`} className="w-48">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {(param.options ?? []).map((opt) => (
                      <SelectItem key={opt.value} value={opt.value}>
                        {opt.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              ) : param.type === "group" ? (
                <Select
                  value={paramState[param.name] === "" ? ANY_GROUP : (paramState[param.name] ?? ANY_GROUP)}
                  onValueChange={(v) => setParam(param.name, v == null || v === ANY_GROUP ? "" : v)}
                >
                  <SelectTrigger id={`param-${param.name}`} className="w-48">
                    <SelectValue placeholder="Any group" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={ANY_GROUP}>Any group</SelectItem>
                    {groups.map((g) => (
                      <SelectItem key={g.id} value={g.id}>
                        {g.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              ) : (
                <Input
                  id={`param-${param.name}`}
                  type="number"
                  className="w-32"
                  value={paramState[param.name] ?? ""}
                  onChange={(e) => setParam(param.name, e.target.value)}
                />
              )}
            </div>
          ))}

          <div className="ml-auto flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => download(key, paramState)}
              disabled={!report}
            >
              <Download className="mr-2 h-4 w-4" />
              CSV
            </Button>
            <Button variant="outline" size="sm" onClick={() => window.print()} disabled={!report}>
              <Printer className="mr-2 h-4 w-4" />
              Print
            </Button>
          </div>
        </div>

        {/* Print-only header: troop name, report title, generated date. */}
        <div className="report-print-header hidden">
          <h1 className="text-xl font-bold">{troopName}</h1>
          <p className="text-lg">{entry.title}</p>
          <p className="text-sm">{new Date().toLocaleDateString()}</p>
        </div>

        <div className="report-print-area">
          {isError ? (
            <p className="text-sm text-destructive">Could not run this report.</p>
          ) : (
            <DataTable
              data={(report?.rows ?? []) as ReportRow[]}
              columns={columns}
              isLoading={isLoading}
              emptyState={
                <p className="text-sm text-muted-foreground">No rows match these parameters.</p>
              }
            />
          )}
        </div>
      </div>
    </>
  )
}
