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

  async function copy() {
    try {
      await navigator.clipboard.writeText(token)
      setCopied(true)
      toast.success("Invite token copied")
      setTimeout(() => setCopied(false), 2000)
    } catch {
      toast.error("Couldn't copy — select and copy manually")
    }
  }

  return (
    <div className="space-y-2 rounded-md border bg-muted/40 p-3">
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-medium">Invite token</span>
        <Button type="button" size="sm" variant="outline" onClick={copy}>
          {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
          {copied ? "Copied" : "Copy"}
        </Button>
      </div>
      <code className="block max-h-24 overflow-auto break-all rounded bg-background p-2 font-mono text-xs">
        {token}
      </code>
      <p className="text-xs text-muted-foreground">
        Send this to the invitee. They sign in, then redeem it to claim their account
        {expiresAt ? ` (expires ${new Date(expiresAt).toLocaleString()})` : ""}.
      </p>
    </div>
  )
}
