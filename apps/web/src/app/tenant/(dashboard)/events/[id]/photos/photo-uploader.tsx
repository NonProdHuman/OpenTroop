"use client"

import { useCallback, useRef, useState } from "react"
import { CheckCircle2, CircleAlert, ImagePlus, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { useStorageUsage, useUploadPhotos, type UploadItem } from "@/hooks/use-event-photos"

const MAX_BATCH = 30

function formatBytes(n: number): string {
  if (n >= 1024 ** 3) return `${(n / 1024 ** 3).toFixed(1)} GB`
  if (n >= 1024 ** 2) return `${(n / 1024 ** 2).toFixed(0)} MB`
  return `${Math.max(1, Math.round(n / 1024))} KB`
}

function ItemRow({ item }: { item: UploadItem }) {
  return (
    <li className="flex items-center gap-2 text-sm" data-testid="upload-item">
      {item.status === "done" ? (
        <CheckCircle2 className="h-4 w-4 shrink-0 text-green-600" />
      ) : item.status === "error" || item.status === "skipped" ? (
        <CircleAlert className="h-4 w-4 shrink-0 text-destructive" />
      ) : (
        <Loader2 className="h-4 w-4 shrink-0 animate-spin text-muted-foreground" />
      )}
      <span className="truncate">{item.name}</span>
      {item.error && <span className="truncate text-xs text-destructive">{item.error}</span>}
    </li>
  )
}

export function PhotoUploader({ eventId }: { eventId: string }) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const { upload, items, isUploading } = useUploadPhotos(eventId)
  const usage = useStorageUsage()

  const handleFiles = useCallback(
    (list: FileList | null) => {
      if (!list || list.length === 0) return
      void upload(Array.from(list).slice(0, MAX_BATCH))
    },
    [upload],
  )

  const doneCount = items.filter((i) => i.status === "done").length

  return (
    <section
      aria-label="Add photos"
      data-testid="photo-uploader"
      className={cn(
        "rounded-lg border border-dashed p-4 transition-colors",
        dragging && "border-primary bg-primary/5",
      )}
      onDragOver={(e) => {
        e.preventDefault()
        setDragging(true)
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault()
        setDragging(false)
        handleFiles(e.dataTransfer.files)
      }}
    >
      <div className="flex flex-wrap items-center gap-3">
        <Button
          size="sm"
          onClick={() => inputRef.current?.click()}
          disabled={isUploading}
          data-testid="add-photos-button"
        >
          {isUploading ? (
            <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
          ) : (
            <ImagePlus className="mr-1.5 h-4 w-4" />
          )}
          {isUploading ? `Uploading ${doneCount}/${items.length}…` : "Add photos"}
        </Button>
        <span className="text-sm text-muted-foreground">
          or drag and drop — photos are resized before upload
        </span>
        {usage.data && (
          <span className="ml-auto text-xs text-muted-foreground" data-testid="storage-usage">
            {formatBytes(usage.data.remaining_bytes)} of {formatBytes(usage.data.quota_bytes)}{" "}
            storage left
          </span>
        )}
      </div>
      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        multiple
        hidden
        data-testid="photo-file-input"
        onChange={(e) => {
          handleFiles(e.target.files)
          e.target.value = ""
        }}
      />
      {items.length > 0 && (
        <ul className="mt-3 max-h-40 space-y-1 overflow-y-auto">
          {items.map((item, i) => (
            <ItemRow key={`${item.name}-${i}`} item={item} />
          ))}
        </ul>
      )}
    </section>
  )
}
