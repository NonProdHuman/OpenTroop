"use client"

import { useState, useRef, useEffect, useCallback, DragEvent, ChangeEvent } from "react"
import { useApi } from "@/lib/api"
import { PageHeader } from "@/components/page-header"
import { Button } from "@/components/ui/button"
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Label } from "@/components/ui/label"
import { ScrollArea } from "@/components/ui/scroll-area"
import { toast } from "sonner"
import {
  Upload,
  File,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Loader2,
  Users,
  UsersRound,
  MapPin,
  Calendar,
  Settings2,
  Heart,
  X
} from "lucide-react"
import type { ImportJob } from "@/types/api"

const TIMEZONES = [
  { value: "America/New_York", label: "Eastern Time (ET) - e.g. New York, Atlanta" },
  { value: "America/Chicago", label: "Central Time (CT) - e.g. Chicago, Houston" },
  { value: "America/Denver", label: "Mountain Time (MT) - e.g. Denver, Salt Lake City" },
  { value: "America/Phoenix", label: "Arizona Time - e.g. Phoenix (No DST)" },
  { value: "America/Los_Angeles", label: "Pacific Time (PT) - e.g. Los Angeles, Seattle" },
  { value: "America/Anchorage", label: "Alaska Time (AKT)" },
  { value: "America/Honolulu", label: "Hawaii Time (HST)" },
  { value: "UTC", label: "Coordinated Universal Time (UTC)" },
]

// Human labels for the importer's stage names (ImportJob.stage).
const STAGE_LABELS: Record<string, string> = {
  patrols: "Creating patrols",
  members: "Importing members",
  relationships: "Linking families",
  positions: "Recording leadership history",
  locations: "Adding locations",
  event_types: "Setting up event types",
  events: "Importing events",
  participants: "Indexing attendance",
  advancement: "Recording advancement",
}

const isActive = (job: ImportJob | null) =>
  job?.status === "queued" || job?.status === "running"

export default function ImportPage() {
  const { request } = useApi()
  const [file, setFile] = useState<File | null>(null)
  const [timezone, setTimezone] = useState("America/New_York")
  const [submitting, setSubmitting] = useState(false)
  const [job, setJob] = useState<ImportJob | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const summary = job?.summary ?? null
  const warnings = job?.warnings ?? []

  // Poll the job while it is queued/running so the panel shows live progress and,
  // when it finishes, the full summary + warnings (which a gateway timeout used to
  // eat). The import runs in the background — closing this page does not cancel it.
  useEffect(() => {
    if (!job || !isActive(job)) return
    let cancelled = false
    const tick = async () => {
      try {
        const next = await request<ImportJob>(`/import/jobs/${job.id}`)
        if (!cancelled) setJob(next)
      } catch {
        // transient — the next tick retries
      }
    }
    const id = setInterval(tick, 1500)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [job, request])

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = () => setIsDragging(false)

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragging(false)
    validateAndSetFile(e.dataTransfer.files[0])
  }

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0]
    if (selectedFile) validateAndSetFile(selectedFile)
  }

  const validateAndSetFile = (selectedFile: File) => {
    const validExtensions = [".xml", ".zip", ".gz"]
    if (!validExtensions.some((ext) => selectedFile.name.toLowerCase().endsWith(ext))) {
      toast.error("Invalid file format. Please upload an XML, ZIP, or GZ file.")
      return
    }
    setFile(selectedFile)
    setJob(null)
  }

  const handleClear = useCallback(() => {
    setFile(null)
    setJob(null)
    if (fileInputRef.current) fileInputRef.current.value = ""
  }, [])

  const handleUpload = async () => {
    if (!file) return
    setSubmitting(true)
    setJob(null)

    const formData = new FormData()
    formData.append("file", file)
    formData.append("timezone", timezone)

    try {
      const queued = await request<ImportJob>("/import/twh", { method: "POST", body: formData })
      setJob(queued)
      toast.success("Import queued — it will keep running even if you leave this page.")
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to queue the TroopWebHost import."
      toast.error(msg)
    } finally {
      setSubmitting(false)
    }
  }

  const showForm = !job
  const showProgress = isActive(job)
  const showSuccess = job?.status === "succeeded"
  const showFailure = job?.status === "failed"

  return (
    <>
      <PageHeader title="Import Data" />
      <div className="flex flex-1 flex-col gap-6 p-6 max-w-4xl mx-auto w-full">
        {showForm && (
          <Card className="border border-border/50 shadow-sm">
            <CardHeader>
              <CardTitle>TroopWebHost XML Import</CardTitle>
              <CardDescription>
                Upload your full-data XML export from TroopWebHost to populate your roster, patrols, locations, events, and attendance records. Large files can be compressed to .zip or .gz to upload faster and bypass size limits.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="rounded-lg border border-amber-500/25 bg-amber-500/[0.03] p-4 text-sm text-amber-800 dark:text-amber-300 flex gap-3">
                <AlertTriangle className="h-5 w-5 text-amber-500 shrink-0 mt-0.5" />
                <div className="space-y-1">
                  <p className="font-medium">File Size Limit Warning (30 MB)</p>
                  <p className="text-xs text-muted-foreground">
                    {"Due to platform hosting limits, files larger than 30 MB must be compressed into a .zip or .gz archive (not .tar.gz) before uploading. Compression reduces file sizes by up to 95% and ensures your upload completes successfully."}
                  </p>
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="timezone">Source Timezone</Label>
                <Select value={timezone} onValueChange={(val) => setTimezone(val ?? "America/New_York")} disabled={submitting}>
                  <SelectTrigger id="timezone" className="w-full">
                    <SelectValue placeholder="Select troop timezone" />
                  </SelectTrigger>
                  <SelectContent>
                    {TIMEZONES.map((tz) => (
                      <SelectItem key={tz.value} value={tz.value}>
                        {tz.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">
                  {"Required to correctly convert your troop's naive timestamps (local time) into UTC."}
                </p>
              </div>

              <div className="space-y-2">
                <Label>Export File (.xml, .zip, .gz)</Label>
                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={handleFileChange}
                  accept=".xml,.zip,.gz"
                  className="hidden"
                  disabled={submitting}
                />

                {!file ? (
                  <div
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onDrop={handleDrop}
                    onClick={() => fileInputRef.current?.click()}
                    className={`flex flex-col items-center justify-center border-2 border-dashed rounded-lg p-10 cursor-pointer transition-colors duration-150 ${
                      isDragging
                        ? "border-primary bg-primary/5 text-primary"
                        : "border-muted-foreground/20 hover:border-muted-foreground/45 bg-card"
                    }`}
                  >
                    <Upload className="h-10 w-10 text-muted-foreground/70 mb-4" />
                    <p className="text-sm font-medium">Click to select or drag & drop</p>
                    <p className="text-xs text-muted-foreground mt-1">TroopWebHost XML, ZIP, or GZ file</p>
                  </div>
                ) : (
                  <div className="flex items-center justify-between border border-border rounded-lg p-4 bg-muted/20">
                    <div className="flex items-center gap-3">
                      <File className="h-8 w-8 text-primary" />
                      <div className="space-y-0.5">
                        <p className="text-sm font-medium max-w-[250px] sm:max-w-md truncate">{file.name}</p>
                        <p className="text-xs text-muted-foreground">
                          {(file.size / (1024 * 1024)).toFixed(2)} MB
                        </p>
                      </div>
                    </div>
                    {!submitting && (
                      <Button variant="ghost" size="icon" onClick={handleClear}>
                        <X className="h-4 w-4" />
                      </Button>
                    )}
                  </div>
                )}
              </div>
            </CardContent>

            <CardFooter className="flex justify-end gap-3 border-t border-border/50 pt-6">
              <Button onClick={handleUpload} disabled={!file || submitting} className="w-full sm:w-auto">
                {submitting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Queuing…
                  </>
                ) : (
                  "Start Import"
                )}
              </Button>
            </CardFooter>
          </Card>
        )}

        {/* Live progress while the background job runs */}
        {showProgress && (
          <Card className="border border-border/50 shadow-sm">
            <CardHeader className="flex flex-row items-center gap-4">
              <Loader2 className="h-7 w-7 animate-spin text-primary shrink-0" />
              <div className="space-y-0.5">
                <CardTitle>
                  {job?.status === "queued" ? "Queued for import" : "Importing your data"}
                </CardTitle>
                <CardDescription>
                  {job?.stage ? STAGE_LABELS[job.stage] ?? job.stage : "Waiting for a worker to pick this up…"}
                  {". "}This runs in the background — you can safely leave this page.
                </CardDescription>
              </div>
            </CardHeader>
            {job?.progress && (
              <CardContent>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
                  <ProgressStat label="Members" value={job.progress.members} />
                  <ProgressStat label="Events" value={job.progress.events} />
                  <ProgressStat label="Attendance" value={job.progress.participants} />
                </div>
              </CardContent>
            )}
          </Card>
        )}

        {/* Failure */}
        {showFailure && (
          <Card className="border-rose-500/30 bg-rose-500/[0.02]">
            <CardHeader className="flex flex-row items-center gap-4">
              <XCircle className="h-8 w-8 text-rose-500 shrink-0" />
              <div className="space-y-0.5">
                <CardTitle className="text-rose-700 dark:text-rose-400">Import Failed</CardTitle>
                <CardDescription>{job?.error ?? "The import could not be completed."}</CardDescription>
              </div>
            </CardHeader>
            <CardFooter className="flex justify-end border-t border-border/30 pt-6">
              <Button variant="outline" onClick={handleClear}>Try Again</Button>
            </CardFooter>
          </Card>
        )}

        {/* Success */}
        {showSuccess && summary && (
          <div className="space-y-6">
            <Card className="border-emerald-500/25 bg-emerald-500/[0.01] shadow-sm">
              <CardHeader className="flex flex-row items-center gap-4">
                <CheckCircle2 className="h-8 w-8 text-emerald-500 shrink-0" />
                <div className="space-y-0.5">
                  <CardTitle className="text-emerald-700 dark:text-emerald-400">Import Completed Successfully</CardTitle>
                  <CardDescription>
                    Your data from TroopWebHost has been parsed and written to the database.
                  </CardDescription>
                </div>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                  <SummaryStat icon={<UsersRound className="h-5 w-5 text-indigo-500" />} value={summary.patrols} label="Patrols Created" />
                  <SummaryStat icon={<Users className="h-5 w-5 text-blue-500" />} value={summary.members} label="Members Created" />
                  <SummaryStat icon={<Heart className="h-5 w-5 text-rose-500" />} value={summary.relationships} label="Relationships" />
                  <SummaryStat icon={<MapPin className="h-5 w-5 text-amber-500" />} value={summary.locations} label="Locations" />
                  <SummaryStat icon={<Settings2 className="h-5 w-5 text-emerald-500" />} value={summary.event_types} label="Event Types" />
                  <SummaryStat icon={<Calendar className="h-5 w-5 text-purple-500" />} value={summary.events} label="Events Imported" />
                </div>

                <div className="mt-4 p-3 border border-border/50 rounded-lg text-xs bg-muted/20 text-muted-foreground flex justify-between">
                  <span>Attendance RSVPs indexed: <strong>{summary.participants}</strong></span>
                  <span>Duplicate records skipped: <strong>{summary.skipped}</strong></span>
                </div>
              </CardContent>
              <CardFooter className="flex justify-end gap-3 border-t border-border/30 pt-6">
                <Button variant="outline" onClick={handleClear}>Import Another File</Button>
                <Button onClick={() => window.location.href = "/members"}>View Roster</Button>
              </CardFooter>
            </Card>

            {warnings.length > 0 && (
              <Card className="border-amber-500/25 bg-amber-500/[0.01]">
                <CardHeader className="flex flex-row items-center gap-3">
                  <AlertTriangle className="h-5 w-5 text-amber-500" />
                  <CardTitle className="text-sm font-semibold text-amber-800 dark:text-amber-400">
                    Import Warnings ({warnings.length})
                  </CardTitle>
                </CardHeader>
                <CardContent className="pt-0">
                  <ScrollArea className="h-48 w-full border rounded-md p-3 bg-card">
                    <ul className="space-y-1.5 list-disc list-inside text-xs text-muted-foreground">
                      {warnings.map((warn, i) => (
                        <li key={i}>{warn}</li>
                      ))}
                    </ul>
                  </ScrollArea>
                </CardContent>
              </Card>
            )}
          </div>
        )}
      </div>
    </>
  )
}

function ProgressStat({ label, value }: { label: string; value?: number | null }) {
  return (
    <div className="flex items-center justify-between p-3 border rounded-lg bg-card">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-semibold tabular-nums">{value ?? 0}</span>
    </div>
  )
}

function SummaryStat({ icon, value, label }: { icon: React.ReactNode; value?: number | null; label: string }) {
  return (
    <div className="flex items-center gap-3 p-4 border rounded-lg bg-card shadow-sm">
      {icon}
      <div>
        <p className="text-2xl font-bold">{value ?? 0}</p>
        <p className="text-xs text-muted-foreground">{label}</p>
      </div>
    </div>
  )
}
