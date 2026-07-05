"use client"

import { useMemo, useState } from "react"
import { useRouter } from "next/navigation"
import { useGroups } from "@/hooks/use-groups"
import { useCreateMessage, useSendMessage } from "@/hooks/use-messages"
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
import type { AudienceType, MessageWithPreview } from "@/types/api"

type Target = { group_id: string; audience_type: AudienceType }

const AUDIENCE_LABELS: Record<AudienceType, string> = {
  members: "Members",
  members_and_parents: "Members + Parents",
  parents_only: "Parents only",
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
  const [targets, setTargets] = useState<Target[]>([])
  const [preview, setPreview] = useState<MessageWithPreview | null>(null)
  const [error, setError] = useState<string | null>(null)

  const availableGroups = useMemo(
    () => groups.filter((g) => !targets.some((t) => t.group_id === g.id)),
    [groups, targets],
  )
  const groupName = (id: string) => groups.find((g) => g.id === id)?.name ?? "Group"

  const canPreview = subject.trim() && body.trim() && targets.length > 0

  const addTarget = (groupId: string) => {
    setTargets((prev) => [...prev, { group_id: groupId, audience_type: "members" }])
    setPreview(null)
  }
  const setAudience = (groupId: string, audience: AudienceType) => {
    setTargets((prev) =>
      prev.map((t) => (t.group_id === groupId ? { ...t, audience_type: audience } : t)),
    )
    setPreview(null)
  }
  const removeTarget = (groupId: string) => {
    setTargets((prev) => prev.filter((t) => t.group_id !== groupId))
    setPreview(null)
  }

  const draft = () =>
    createMessage.mutateAsync({
      subject,
      body,
      send_email: sendEmail,
      send_push: sendPush,
      group_targets: targets,
      scheduled_at: null,
    })

  const runPreview = async () => {
    setError(null)
    try {
      setPreview(await draft())
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not build a preview.")
    }
  }

  const send = async () => {
    setError(null)
    try {
      const created = preview ?? (await draft())
      await sendMessage.mutateAsync(created.message.id)
      router.push("/messages")
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not send the message.")
    }
  }

  const busy = createMessage.isPending || sendMessage.isPending

  return (
    <>
      <PageHeader title="New announcement" />
      <div className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-4 p-4">
        <div className="flex flex-col gap-1">
          <Label htmlFor="subject">Subject</Label>
          <Input
            id="subject"
            value={subject}
            onChange={(e) => {
              setSubject(e.target.value)
              setPreview(null)
            }}
            placeholder="Campout reminder"
          />
        </div>

        <div className="flex flex-col gap-1">
          <Label htmlFor="body">Message</Label>
          <Textarea
            id="body"
            value={body}
            onChange={(e) => {
              setBody(e.target.value)
              setPreview(null)
            }}
            rows={6}
            placeholder="Don't forget rain gear and a full water bottle."
          />
        </div>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Recipients</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {targets.map((target) => (
              <div key={target.group_id} className="flex items-center gap-2">
                <span className="min-w-0 flex-1 truncate text-sm font-medium">
                  {groupName(target.group_id)}
                </span>
                <Select
                  value={target.audience_type}
                  onValueChange={(v) => setAudience(target.group_id, (v ?? "members") as AudienceType)}
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
                <Button variant="ghost" size="sm" onClick={() => removeTarget(target.group_id)}>
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
                Add at least one group to choose who receives this.
              </p>
            )}
          </CardContent>
        </Card>

        <div className="flex flex-wrap items-center gap-4">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={sendEmail}
              onChange={(e) => {
                setSendEmail(e.target.checked)
                setPreview(null)
              }}
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

        {preview && (
          <Card>
            <CardContent className="flex flex-wrap items-center gap-3 py-3 text-sm">
              <Badge variant="secondary">{preview.preview.total} recipients</Badge>
              {sendEmail && <span>📧 {preview.preview.email} email</span>}
              {sendPush && <span>📱 {preview.preview.push_devices} devices</span>}
              {preview.preview.opted_out > 0 && (
                <span className="text-muted-foreground">{preview.preview.opted_out} opted out</span>
              )}
              {preview.preview.bounced > 0 && (
                <span className="text-muted-foreground">{preview.preview.bounced} bounced</span>
              )}
              {preview.preview.no_email > 0 && (
                <span className="text-muted-foreground">{preview.preview.no_email} no email</span>
              )}
            </CardContent>
          </Card>
        )}

        {error && <p className="text-destructive text-sm">{error}</p>}

        <div className="flex items-center gap-2">
          <Button variant="outline" disabled={!canPreview || busy} onClick={runPreview}>
            Preview recipients
          </Button>
          <Button disabled={!canPreview || busy} onClick={send}>
            {busy ? "Sending…" : "Send now"}
          </Button>
        </div>
      </div>
    </>
  )
}
