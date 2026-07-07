"use client"

import { useMemo, useState } from "react"
import { useRouter } from "next/navigation"
import { ChevronDown } from "lucide-react"
import { useGroups } from "@/hooks/use-groups"
import { useCreateMessage, useRecipientPreviewFor, useSendMessage } from "@/hooks/use-messages"
import { PageHeader } from "@/components/page-header"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"
import type { AudienceType, MessageDelivery, RecipientPreviewRequest } from "@/types/api"

type Target = { group_id: string; audience_type: AudienceType }

const AUDIENCE_LABELS: Record<AudienceType, string> = {
  members: "Members",
  members_and_parents: "Members + Parents",
  parents_only: "Parents only",
}

// Skipped email states, shown as a short note next to a recipient.
const EMAIL_SKIP_NOTE: Record<string, string> = {
  skipped_opt_out: "opted out",
  skipped_bounced: "bounced",
  skipped_no_email: "no email",
}

export default function ComposeMessagePage() {
  const router = useRouter()
  const { data: groups = [] } = useGroups()
  const createMessage = useCreateMessage()
  const sendMessage = useSendMessage()

  const [subject, setSubject] = useState("")
  const [body, setBody] = useState("")
  const [sendEmail, setSendEmail] = useState(true)
  const [sendPush, setSendPush] = useState(true)
  const [sendToAll, setSendToAll] = useState(false)
  const [delivery, setDelivery] = useState<MessageDelivery>("immediate")
  const [targets, setTargets] = useState<Target[]>([])
  const [panelOpen, setPanelOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const availableGroups = useMemo(
    () => groups.filter((g) => !targets.some((t) => t.group_id === g.id)),
    [groups, targets],
  )
  const groupName = (id: string) => groups.find((g) => g.id === id)?.name ?? "Group"

  const addTarget = (groupId: string) =>
    setTargets((prev) => [...prev, { group_id: groupId, audience_type: "members" }])
  const setAudience = (groupId: string, audience: AudienceType) =>
    setTargets((prev) =>
      prev.map((t) => (t.group_id === groupId ? { ...t, audience_type: audience } : t)),
    )
  const removeTarget = (groupId: string) =>
    setTargets((prev) => prev.filter((t) => t.group_id !== groupId))

  const hasAudience = sendToAll || targets.length > 0

  // Live recipient preview — resolves who this reaches without saving a draft.
  const previewBody: RecipientPreviewRequest | null = useMemo(() => {
    if (!hasAudience) return null
    return {
      send_to_all: sendToAll,
      group_targets: sendToAll ? [] : targets,
      send_email: sendEmail,
      send_push: sendPush,
      delivery,
    }
  }, [hasAudience, sendToAll, targets, sendEmail, sendPush, delivery])

  const { data: preview, isFetching: previewLoading } = useRecipientPreviewFor(previewBody)

  const canSend = Boolean(subject.trim() && body.trim() && hasAudience)
  const busy = createMessage.isPending || sendMessage.isPending

  const send = async () => {
    setError(null)
    try {
      const created = await createMessage.mutateAsync({
        subject,
        body,
        send_email: sendEmail,
        send_push: sendPush,
        send_to_all: sendToAll,
        group_targets: sendToAll ? [] : targets,
        delivery,
        scheduled_at: null,
      })
      await sendMessage.mutateAsync(created.message.id)
      router.push("/messages")
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not send the message.")
    }
  }

  return (
    <>
      <PageHeader title="New announcement" />
      <div className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-4 p-4">
        <div className="flex flex-col gap-1">
          <Label htmlFor="subject">Subject</Label>
          <Input
            id="subject"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            placeholder="Campout reminder"
          />
        </div>

        <div className="flex flex-col gap-1">
          <Label htmlFor="body">Message</Label>
          <Textarea
            id="body"
            value={body}
            onChange={(e) => setBody(e.target.value)}
            rows={6}
            placeholder="Don't forget rain gear and a full water bottle."
          />
        </div>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Recipients</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <label className="flex items-center gap-2 text-sm font-medium">
              <input
                type="checkbox"
                checked={sendToAll}
                onChange={(e) => setSendToAll(e.target.checked)}
              />
              Send to the entire troop
            </label>

            {sendToAll ? (
              <p className="text-muted-foreground text-sm">
                Everyone in the troop will receive this announcement.
              </p>
            ) : (
              <>
                {targets.map((target) => (
                  <div key={target.group_id} className="flex items-center gap-2">
                    <span className="min-w-0 flex-1 truncate text-sm font-medium">
                      {groupName(target.group_id)}
                    </span>
                    <Select
                      value={target.audience_type}
                      onValueChange={(v) =>
                        setAudience(target.group_id, (v ?? "members") as AudienceType)
                      }
                    >
                      <SelectTrigger className="h-8 w-48">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {(Object.keys(AUDIENCE_LABELS) as AudienceType[]).map((a) => (
                          <SelectItem key={a} value={a}>
                            {AUDIENCE_LABELS[a]}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => removeTarget(target.group_id)}
                    >
                      Remove
                    </Button>
                  </div>
                ))}
                {availableGroups.length > 0 && (
                  <Select value="" onValueChange={(v) => v && addTarget(v)}>
                    <SelectTrigger className="h-8 w-64">
                      <SelectValue placeholder="Add a group…" />
                    </SelectTrigger>
                    <SelectContent>
                      {availableGroups.map((g) => (
                        <SelectItem key={g.id} value={g.id}>
                          {g.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
                {targets.length === 0 && (
                  <p className="text-muted-foreground text-sm">
                    Add a group, or send to the entire troop.
                  </p>
                )}
              </>
            )}
          </CardContent>
        </Card>

        <div className="flex flex-wrap items-center gap-4">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={sendEmail}
              onChange={(e) => setSendEmail(e.target.checked)}
            />
            Email
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={sendPush}
              onChange={(e) => setSendPush(e.target.checked)}
            />
            Push notification
          </label>
        </div>

        {/* Email delivery timing (GH-218). Inbox + push always fire immediately;
            this only controls when the email copy goes out. */}
        <div className="flex flex-col gap-1">
          <Label htmlFor="delivery">Email delivery</Label>
          <Select
            value={delivery}
            onValueChange={(v) => setDelivery((v ?? "immediate") as MessageDelivery)}
          >
            <SelectTrigger id="delivery" className="w-72">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="immediate">Send now</SelectItem>
              <SelectItem value="digest">Include in next newsletter</SelectItem>
            </SelectContent>
          </Select>
          <p className="text-muted-foreground text-sm">
            {delivery === "digest"
              ? "The inbox post and push alert go out now; the email is held for the troop's next weekly newsletter."
              : "The email goes out right away, alongside the inbox post and push alert."}
          </p>
        </div>

        {/* Always-on, live recipient list (collapsible). */}
        <Card>
          <button
            type="button"
            onClick={() => setPanelOpen((o) => !o)}
            className="flex w-full items-center justify-between gap-2 px-4 py-3 text-left"
            aria-expanded={panelOpen}
          >
            <span className="text-sm font-medium">
              Review recipients{preview ? ` · ${preview.preview.total}` : ""}
            </span>
            <ChevronDown
              className={cn("h-4 w-4 transition-transform", panelOpen && "rotate-180")}
            />
          </button>
          {panelOpen && (
            <CardContent className="border-t pt-3">
              {!hasAudience ? (
                <p className="text-muted-foreground text-sm">
                  Choose recipients above to see who this reaches.
                </p>
              ) : previewLoading && !preview ? (
                <p className="text-muted-foreground text-sm">Resolving recipients…</p>
              ) : preview ? (
                <div className="space-y-3">
                  <div className="flex flex-wrap items-center gap-3 text-sm">
                    <Badge variant="secondary">{preview.preview.total} recipients</Badge>
                    {sendEmail && <span>📧 {preview.preview.email} email</span>}
                    {sendPush && <span>📱 {preview.preview.push_devices} devices</span>}
                    {preview.preview.opted_out > 0 && (
                      <span className="text-muted-foreground">
                        {preview.preview.opted_out} opted out
                      </span>
                    )}
                    {preview.preview.bounced > 0 && (
                      <span className="text-muted-foreground">
                        {preview.preview.bounced} bounced
                      </span>
                    )}
                    {preview.preview.no_email > 0 && (
                      <span className="text-muted-foreground">
                        {preview.preview.no_email} no email
                      </span>
                    )}
                  </div>
                  {preview.recipients.length === 0 ? (
                    <p className="text-muted-foreground text-sm">No one matches yet.</p>
                  ) : (
                    <ul className="max-h-64 divide-y overflow-y-auto rounded-md border text-sm">
                      {preview.recipients.map((r) => (
                        <li
                          key={r.member_id}
                          className="flex items-center justify-between gap-2 px-3 py-1.5"
                        >
                          <span className="min-w-0 truncate">
                            {r.first_name} {r.last_name}
                          </span>
                          <span className="text-muted-foreground flex shrink-0 items-center gap-2 text-xs">
                            {r.has_push_device && <span title="Has a push device">📱</span>}
                            {EMAIL_SKIP_NOTE[r.email_state] && (
                              <span>{EMAIL_SKIP_NOTE[r.email_state]}</span>
                            )}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              ) : null}
            </CardContent>
          )}
        </Card>

        {error && <p className="text-destructive text-sm">{error}</p>}

        <div className="flex items-center gap-2">
          <Button disabled={!canSend || busy} onClick={send}>
            {busy ? "Sending…" : delivery === "digest" ? "Post announcement" : "Send now"}
          </Button>
        </div>
      </div>
    </>
  )
}
