"use client"

import { Calendar, Check, Copy, Info, Loader2 } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"
import { Button, buttonVariants } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { useCalendarSubscription } from "@/hooks/use-calendar-subscription"
import { cn } from "@/lib/utils"

export function CalendarSubscriptionDialog() {
  const [open, setOpen] = useState(false)
  const [copied, setCopied] = useState(false)
  const [showRotateConfirm, setShowRotateConfirm] = useState(false)

  const {
    subscription,
    isLoading,
    error,
    rotate,
    isRotating,
  } = useCalendarSubscription()

  const feedPath = subscription?.feed_path || ""
  const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
  const httpUrl = feedPath ? `${base}${feedPath}` : ""
  const webcalUrl = httpUrl ? httpUrl.replace(/^https?:\/\//, "webcal://") : ""

  async function copyLink() {
    if (!httpUrl) return
    try {
      await navigator.clipboard.writeText(httpUrl)
      setCopied(true)
      toast.success("Calendar feed URL copied")
      setTimeout(() => setCopied(false), 2000)
    } catch {
      toast.error("Couldn't copy link — select and copy manually")
    }
  }

  function handleRotate() {
    rotate(undefined, {
      onSuccess: () => {
        setShowRotateConfirm(false)
      },
    })
  }

  function handleOpenChange(next: boolean) {
    setOpen(next)
    if (!next) {
      setShowRotateConfirm(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger
        render={
          <Button variant="outline" size="sm" className="gap-2">
            <Calendar className="h-4 w-4 text-muted-foreground" />
            <span>Subscribe</span>
          </Button>
        }
      />
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-full bg-amber-50 dark:bg-amber-950/30">
            <Calendar className="h-5 w-5 text-amber-600 dark:text-amber-400" />
          </div>
          <DialogTitle className="text-center mt-2 font-semibold">Subscribe to Calendar</DialogTitle>
          <DialogDescription className="text-center text-xs">
            Sync your troop events directly to Apple Calendar, Google Calendar, Outlook, or any standard calendar app.
          </DialogDescription>
        </DialogHeader>

        {isLoading ? (
          <div className="flex flex-col items-center justify-center py-6">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            <span className="text-xs text-muted-foreground mt-2">Loading calendar feed URL...</span>
          </div>
        ) : error ? (
          <div className="text-center text-xs text-destructive py-4">
            Failed to load calendar subscription. Please try again.
          </div>
        ) : (
          <div className="space-y-4 py-2">
            {!feedPath ? (
              <div className="rounded-lg border border-border bg-muted/20 p-3 space-y-1 text-xs">
                <div className="flex items-center gap-1.5 font-medium text-foreground">
                  <Info className="h-3.5 w-3.5 text-muted-foreground" />
                  <span>Your calendar feed is active</span>
                </div>
                <p className="text-[11px] text-muted-foreground leading-snug">
                  For security, the feed link is shown only when it is created. If you no
                  longer have it, reset the link below to get a new one.
                </p>
              </div>
            ) : (
            <>
            <div className="space-y-2">
              <a
                href={webcalUrl}
                target="_blank"
                rel="noopener noreferrer"
                className={cn(
                  buttonVariants({ variant: "default", size: "default" }),
                  "w-full bg-amber-600 hover:bg-amber-700 text-white border-transparent gap-2 dark:bg-amber-500 dark:hover:bg-amber-600 dark:text-slate-950 font-semibold"
                )}
              >
                <Calendar className="h-4 w-4" />
                Subscribe in Calendar App
              </a>
              <p className="text-[10px] text-center text-muted-foreground leading-snug">
                This is a personal feed containing your troop-wide and patrol-specific events. Events you decline are automatically excluded.
              </p>
            </div>

            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <span className="w-full border-t border-border" />
              </div>
              <div className="relative flex justify-center text-xs uppercase">
                <span className="bg-popover px-2 text-muted-foreground text-[10px]">Or subscribe manually</span>
              </div>
            </div>

            <div className="space-y-1">
              <label htmlFor="calendar-feed-url" className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                Calendar Feed URL
              </label>
              <div className="flex gap-2">
                <Input
                  id="calendar-feed-url"
                  readOnly
                  value={httpUrl}
                  className="font-mono text-xs select-all bg-muted/40 h-8"
                  onClick={(e) => (e.target as HTMLInputElement).select()}
                />
                <Button size="icon" variant="outline" className="shrink-0 h-8 w-8" onClick={copyLink}>
                  {copied ? <Check className="h-4 w-4 text-green-600 dark:text-green-400" /> : <Copy className="h-4 w-4" />}
                </Button>
              </div>
            </div>

            <div className="rounded-lg border border-border bg-muted/20 p-3 space-y-2 text-xs">
              <div className="flex items-center gap-1.5 font-medium text-foreground">
                <Info className="h-3.5 w-3.5 text-muted-foreground" />
                <span>How to use this link</span>
              </div>
              <ul className="list-disc pl-4 space-y-1 text-muted-foreground text-[11px]">
                <li>
                  <strong className="text-foreground">Google Calendar:</strong> Click &ldquo;+&rdquo; next to &ldquo;Other calendars&rdquo; &rarr; &ldquo;From URL&rdquo; &rarr; Paste URL.
                </li>
                <li>
                  <strong className="text-foreground">Apple Calendar:</strong> Click &ldquo;File&rdquo; &rarr; &ldquo;New Calendar Subscription...&rdquo; &rarr; Paste URL.
                </li>
                <li>
                  <strong className="text-foreground">Outlook / Live:</strong> Click &ldquo;Add Calendar&rdquo; &rarr; &ldquo;Subscribe from web&rdquo; &rarr; Paste URL.
                </li>
              </ul>
            </div>
            </>
            )}

            <div className="border-t border-border pt-4">
              {showRotateConfirm ? (
                <div className="rounded-lg border border-destructive/20 bg-destructive/5 p-3 space-y-3">
                  <div className="space-y-1">
                    <h4 className="text-xs font-semibold text-destructive">Are you absolutely sure?</h4>
                    <p className="text-[11px] text-muted-foreground leading-snug">
                      Your existing calendar subscriptions will stop syncing immediately. You will need to add the new link to all your calendar apps.
                    </p>
                  </div>
                  <div className="flex gap-2 justify-end">
                    <Button
                      size="xs"
                      variant="ghost"
                      onClick={() => setShowRotateConfirm(false)}
                      disabled={isRotating}
                    >
                      Cancel
                    </Button>
                    <Button
                      size="xs"
                      variant="destructive"
                      onClick={handleRotate}
                      disabled={isRotating}
                    >
                      {isRotating ? "Resetting..." : "Yes, reset link"}
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">Link compromised or not syncing?</span>
                  <Button
                    variant="link"
                    className="text-destructive h-auto p-0 text-xs hover:no-underline font-medium"
                    onClick={() => setShowRotateConfirm(true)}
                  >
                    Reset link
                  </Button>
                </div>
              )}
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
