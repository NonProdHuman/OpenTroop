"use client"

import { Check, Copy } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"

/**
 * Shows a freshly-minted invite/claim token with a copy button. Until automated
 * email delivery exists, the platform admin hands this token to the invitee
 * out-of-band; they redeem it via the app's claim flow after signing in.
 */
export function InviteTokenDisplay({ token, expiresAt }: { token: string; expiresAt?: string }) {
  const [copied, setCopied] = useState(false)

  // Use the origin if available, otherwise fallback to a generic placeholder.
  // In a real app we might pass NEXT_PUBLIC_APP_URL, but window.location is fine for a client component.
  const baseUrl = typeof window !== "undefined" ? window.location.origin : "https://app.opentroop.app"
  const claimUrl = `${baseUrl}/claim?token=${token}`

  async function copy() {
    try {
      await navigator.clipboard.writeText(claimUrl)
      setCopied(true)
      toast.success("Invite link copied")
      setTimeout(() => setCopied(false), 2000)
    } catch {
      toast.error("Couldn't copy — select and copy manually")
    }
  }

  return (
    <div className="space-y-3 rounded-md border bg-muted/40 p-4">
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-medium">Invite Link</span>
        <div className="flex items-center gap-2">
          <Button type="button" size="sm" variant="outline" onClick={copy}>
            {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
            {copied ? "Copied" : "Copy"}
          </Button>
          <Button type="button" size="sm" render={<a href={claimUrl} target="_blank" rel="noopener noreferrer" />} nativeButton={false}>
            Claim Now
          </Button>
        </div>
      </div>
      <code className="block max-h-24 overflow-auto break-all rounded bg-background p-2 font-mono text-xs">
        {claimUrl}
      </code>
      <p className="text-xs text-muted-foreground">
        Send this link to the invitee. They will sign in and redeem it to claim their account
        {expiresAt ? ` (expires ${new Date(expiresAt).toLocaleString()})` : ""}.
      </p>
    </div>
  )
}
