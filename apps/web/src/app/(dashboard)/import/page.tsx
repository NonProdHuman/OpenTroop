"use client"

import { useState, useRef, DragEvent, ChangeEvent } from "react"
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
  Loader2,
  Users,
  UsersRound,
  MapPin,
  Calendar,
  Settings2,
  Heart,
  X
} from "lucide-react"
import type { TwhImportRead } from "@/types/api"

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

export default function ImportPage() {
  const { request } = useApi()
  const [file, setFile] = useState<File | null>(null)
  const [timezone, setTimezone] = useState("America/New_York")
  const [isLoading, setIsLoading] = useState(false)
  const [result, setResult] = useState<TwhImportRead | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = () => {
    setIsDragging(false)
  }

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragging(false)
    const droppedFile = e.dataTransfer.files[0]
    validateAndSetFile(droppedFile)
  }

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0]
    if (selectedFile) {
      validateAndSetFile(selectedFile)
    }
  }

  const validateAndSetFile = (selectedFile: File) => {
    if (!selectedFile.name.endsWith(".xml")) {
      toast.error("Invalid file format. Please upload a TroopWebHost XML export file.")
      return
    }
    setFile(selectedFile)
    setResult(null)
  }

  const handleClear = () => {
    setFile(null)
    setResult(null)
    if (fileInputRef.current) {
      fileInputRef.current.value = ""
    }
  }

  const handleUpload = async () => {
    if (!file) return

    setIsLoading(true)
    setResult(null)

    const formData = new FormData()
    formData.append("file", file)
    formData.append("timezone", timezone)

    try {
      const data = await request<TwhImportRead>("/import/twh", {
        method: "POST",
        body: formData,
      })
      setResult(data)
      toast.success("TroopWebHost data imported successfully!")
    } catch (err) {
      console.error(err)
      const msg = err instanceof Error ? err.message : "Failed to import TroopWebHost XML data."
      toast.error(msg)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <>
      <PageHeader title="Import Data" />
      <div className="flex flex-1 flex-col gap-6 p-6 max-w-4xl mx-auto w-full">
        {!result && (
          <Card className="border border-border/50 shadow-sm">
            <CardHeader>
              <CardTitle>TroopWebHost XML Import</CardTitle>
              <CardDescription>
                Upload your full-data XML export from TroopWebHost to populate your roster, patrols, locations, events, and attendance records.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Timezone Selection */}
              <div className="space-y-2">
                <Label htmlFor="timezone">Source Timezone</Label>
                <Select value={timezone} onValueChange={(val) => setTimezone(val ?? "America/New_York")} disabled={isLoading}>
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

              {/* Upload Dropzone */}
              <div className="space-y-2">
                <Label>Export File (.xml)</Label>
                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={handleFileChange}
                  accept=".xml"
                  className="hidden"
                  disabled={isLoading}
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
                    <p className="text-xs text-muted-foreground mt-1">TroopWebHost full-data XML file</p>
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
                    {!isLoading && (
                      <Button variant="ghost" size="icon" onClick={handleClear}>
                        <X className="h-4 w-4" />
                      </Button>
                    )}
                  </div>
                )}
              </div>
            </CardContent>

            <CardFooter className="flex justify-end gap-3 border-t border-border/50 pt-6">
              <Button
                onClick={handleUpload}
                disabled={!file || isLoading}
                className="w-full sm:w-auto"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Importing Data...
                  </>
                ) : (
                  "Start Import"
                )}
              </Button>
            </CardFooter>
          </Card>
        )}

        {/* Loading details overlay */}
        {isLoading && (
          <div className="flex flex-col items-center justify-center p-12 text-center space-y-4">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
            <div className="space-y-1">
              <p className="text-sm font-medium">Parsing XML and populating database</p>
              <p className="text-xs text-muted-foreground max-w-xs">
                This is mapping relationships, creating events, and indexing attendees. Please do not close or refresh this page.
              </p>
            </div>
          </div>
        )}

        {/* Successful results card */}
        {result && (
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
                  {/* Patrols / Groups */}
                  <div className="flex items-center gap-3 p-4 border rounded-lg bg-card shadow-sm">
                    <UsersRound className="h-5 w-5 text-indigo-500" />
                    <div>
                      <p className="text-2xl font-bold">{result.patrols}</p>
                      <p className="text-xs text-muted-foreground">Patrols Created</p>
                    </div>
                  </div>

                  {/* Members */}
                  <div className="flex items-center gap-3 p-4 border rounded-lg bg-card shadow-sm">
                    <Users className="h-5 w-5 text-blue-500" />
                    <div>
                      <p className="text-2xl font-bold">{result.members}</p>
                      <p className="text-xs text-muted-foreground">Members Created</p>
                    </div>
                  </div>

                  {/* Family Connections */}
                  <div className="flex items-center gap-3 p-4 border rounded-lg bg-card shadow-sm">
                    <Heart className="h-5 w-5 text-rose-500" />
                    <div>
                      <p className="text-2xl font-bold">{result.relationships}</p>
                      <p className="text-xs text-muted-foreground">Relationships</p>
                    </div>
                  </div>

                  {/* Locations */}
                  <div className="flex items-center gap-3 p-4 border rounded-lg bg-card shadow-sm">
                    <MapPin className="h-5 w-5 text-amber-500" />
                    <div>
                      <p className="text-2xl font-bold">{result.locations}</p>
                      <p className="text-xs text-muted-foreground">Locations</p>
                    </div>
                  </div>

                  {/* Event Types */}
                  <div className="flex items-center gap-3 p-4 border rounded-lg bg-card shadow-sm">
                    <Settings2 className="h-5 w-5 text-emerald-500" />
                    <div>
                      <p className="text-2xl font-bold">{result.event_types}</p>
                      <p className="text-xs text-muted-foreground">Event Types</p>
                    </div>
                  </div>

                  {/* Events */}
                  <div className="flex items-center gap-3 p-4 border rounded-lg bg-card shadow-sm">
                    <Calendar className="h-5 w-5 text-purple-500" />
                    <div>
                      <p className="text-2xl font-bold">{result.events}</p>
                      <p className="text-xs text-muted-foreground">Events Imported</p>
                    </div>
                  </div>
                </div>

                <div className="mt-4 p-3 border border-border/50 rounded-lg text-xs bg-muted/20 text-muted-foreground flex justify-between">
                  <span>Attendance RSVPs indexed: <strong>{result.participants}</strong></span>
                  <span>Duplicate records skipped: <strong>{result.skipped}</strong></span>
                </div>
              </CardContent>
              <CardFooter className="flex justify-end gap-3 border-t border-border/30 pt-6">
                <Button variant="outline" onClick={handleClear}>
                  Import Another File
                </Button>
                <Button onClick={() => window.location.href = "/members"}>
                  View Roster
                </Button>
              </CardFooter>
            </Card>

            {/* Warnings section if present */}
            {result.warnings && result.warnings.length > 0 && (
              <Card className="border-amber-500/25 bg-amber-500/[0.01]">
                <CardHeader className="flex flex-row items-center gap-3">
                  <AlertTriangle className="h-5 w-5 text-amber-500" />
                  <CardTitle className="text-sm font-semibold text-amber-800 dark:text-amber-400">
                    Import Warnings ({result.warnings.length})
                  </CardTitle>
                </CardHeader>
                <CardContent className="pt-0">
                  <ScrollArea className="h-48 w-full border rounded-md p-3 bg-card">
                    <ul className="space-y-1.5 list-disc list-inside text-xs text-muted-foreground">
                      {result.warnings.map((warn, i) => (
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
