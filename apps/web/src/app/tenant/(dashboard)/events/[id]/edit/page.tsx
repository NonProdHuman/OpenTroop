"use client"

import { useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { X, ChevronsUpDown, Check } from "lucide-react"
import { PageHeader } from "@/components/page-header"
import { Button, buttonVariants } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command"
import { cn } from "@/lib/utils"
import { apiErrorMessage } from "@/lib/api"
import {
  useEvent,
  useUpdateEvent,
  useEventTypes,
  useLocations,
  useEventAudiences,
  useAddEventAudience,
  useRemoveEventAudience,
  useEventOrganizers,
  useAddEventOrganizer,
  useRemoveEventOrganizer,
} from "@/hooks/use-events"
import { useGroups } from "@/hooks/use-groups"
import { useMembers } from "@/hooks/use-members"
import { SectionTitle } from "@/components/form-helpers"
import {
  EventFormFields,
  toApiPayload,
  toFormState,
  type FormState,
} from "../../event-form"
import { EventRsvpAdmin } from "./event-rsvp-admin"
import type { Event } from "@/types/api"

export default function EventEditPage() {
  const { id } = useParams<{ id: string }>()
  const { data: event, isLoading } = useEvent(id)

  if (isLoading || !event) {
    return <div className="p-6 text-muted-foreground text-sm">Loading…</div>
  }

  return <EventEditForm id={id} event={event} />
}

function EventEditForm({ id, event }: { id: string; event: Event }) {
  const router = useRouter()
  const updateEvent = useUpdateEvent()
  const { data: eventTypes = [] } = useEventTypes()
  const { data: locations = [] } = useLocations()

  // Active types, but keep the event's current type available even if disabled.
  const activeTypes = eventTypes.filter((t) => t.is_active || t.id === event.event_type_id)

  const [form, setForm] = useState<FormState>(() => toFormState(event))
  const [error, setError] = useState<string | null>(null)

  const effectiveTypeId = form.event_type_id || activeTypes[0]?.id || ""

  function set<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  function handleSave() {
    if (!form.name.trim()) {
      setError("Event name is required.")
      return
    }
    if (!effectiveTypeId) {
      setError("Select an event type. (Manage types in Settings.)")
      return
    }
    if (!form.scheduled_start || !form.scheduled_end) {
      setError("Start and end times are required.")
      return
    }
    if (new Date(form.scheduled_end) < new Date(form.scheduled_start)) {
      setError("End time cannot be before the start time.")
      return
    }
    setError(null)
    updateEvent.mutate(
      { id, data: toApiPayload(form, effectiveTypeId) },
      {
        onSuccess: () => router.push("/events"),
        onError: (err) => {
          setError(apiErrorMessage(err, { 403: "You don't have permission to edit events." }))
        },
      },
    )
  }

  return (
    <>
      <PageHeader title={`Edit — ${event.name}`}>
        <Button variant="outline" onClick={() => router.push("/events")}>
          Cancel
        </Button>
        <Button onClick={handleSave} disabled={updateEvent.isPending}>
          {updateEvent.isPending ? "Saving…" : "Save"}
        </Button>
      </PageHeader>

      <div className="max-w-2xl mx-auto p-4 md:p-6">
        <Tabs defaultValue="details" className="gap-6">
          <TabsList>
            <TabsTrigger value="details">Details</TabsTrigger>
            <TabsTrigger value="rsvp">RSVP</TabsTrigger>
          </TabsList>

          <TabsContent value="details" className="space-y-6">
            {error && <p className="text-sm text-destructive">{error}</p>}

            <EventFormFields
              form={form}
              set={set}
              eventTypes={activeTypes}
              locations={locations}
              effectiveTypeId={effectiveTypeId}
              showActivity
            />

            <AudienceEditor eventId={id} />
            <OrganizerEditor eventId={id} />

            <div className="flex justify-end gap-3 pt-2">
              <Button variant="outline" onClick={() => router.push("/events")}>
                Cancel
              </Button>
              <Button onClick={handleSave} disabled={updateEvent.isPending}>
                {updateEvent.isPending ? "Saving…" : "Save changes"}
              </Button>
            </div>
          </TabsContent>

          <TabsContent value="rsvp" className="space-y-4">
            <EventRsvpAdmin event={event} />
          </TabsContent>
        </Tabs>
      </div>
    </>
  )
}

// ---------------------------------------------------------------------------
// Audiences (visibility groups) — immediate-persist sub-resource
// ---------------------------------------------------------------------------

function Bubble({ label, onRemove }: { label: string; onRemove: () => void }) {
  return (
    <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium border border-border">
      {label}
      <button
        type="button"
        onClick={onRemove}
        className="ml-0.5 rounded-full hover:opacity-70"
        aria-label={`Remove ${label}`}
      >
        <X className="h-3 w-3" />
      </button>
    </span>
  )
}

function AddCombobox({
  triggerLabel,
  placeholder,
  emptyText,
  options,
  onSelect,
}: {
  triggerLabel: string
  placeholder: string
  emptyText: string
  options: { id: string; label: string }[]
  onSelect: (id: string) => void
}) {
  const [open, setOpen] = useState(false)
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        role="combobox"
        aria-expanded={open}
        className={cn(buttonVariants({ variant: "outline", size: "sm" }), "h-7 gap-1.5 text-xs")}
      >
        <ChevronsUpDown className="h-3 w-3" />
        {triggerLabel}
      </PopoverTrigger>
      <PopoverContent className="w-64 p-0" align="start">
        <Command>
          <CommandInput placeholder={placeholder} className="h-8" />
          <CommandList>
            <CommandEmpty>{emptyText}</CommandEmpty>
            <CommandGroup>
              {options.map((o) => (
                <CommandItem
                  key={o.id}
                  value={o.label}
                  onSelect={() => {
                    onSelect(o.id)
                    setOpen(false)
                  }}
                  className="gap-2"
                >
                  <span>{o.label}</span>
                  <Check className="h-3.5 w-3.5 opacity-0" />
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}

function AudienceEditor({ eventId }: { eventId: string }) {
  const { data: audiences = [] } = useEventAudiences(eventId)
  const { data: groups = [] } = useGroups()
  const addAudience = useAddEventAudience(eventId)
  const removeAudience = useRemoveEventAudience(eventId)

  const groupById = new Map(groups.map((g) => [g.id, g]))
  const selectedIds = new Set(audiences.map((a) => a.group_id))
  const addable = groups.filter((g) => !selectedIds.has(g.id))

  return (
    <div className="space-y-2">
      <SectionTitle>Audience</SectionTitle>
      <p className="text-xs text-muted-foreground">
        {audiences.length === 0
          ? "No groups selected — this event is visible troop-wide."
          : "Visible only to members of these groups (plus event managers)."}
      </p>
      <div className="flex flex-wrap gap-1.5 min-h-[2rem] items-center">
        {audiences.map((a) => (
          <Bubble
            key={a.id}
            label={groupById.get(a.group_id)?.name ?? "Unknown group"}
            onRemove={() => removeAudience.mutate(a.group_id)}
          />
        ))}
      </div>
      {addable.length > 0 && (
        <AddCombobox
          triggerLabel="Add group…"
          placeholder="Search groups…"
          emptyText="No groups found."
          options={addable.map((g) => ({ id: g.id, label: g.name }))}
          onSelect={(id) => addAudience.mutate(id)}
        />
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Organizers — immediate-persist sub-resource
// ---------------------------------------------------------------------------

function OrganizerEditor({ eventId }: { eventId: string }) {
  const { data: organizers = [] } = useEventOrganizers(eventId)
  const { data: members = [] } = useMembers()
  const addOrganizer = useAddEventOrganizer(eventId)
  const removeOrganizer = useRemoveEventOrganizer(eventId)

  const memberById = new Map(members.map((m) => [m.id, m]))
  const selectedIds = new Set(organizers.map((o) => o.member_id))
  const addable = members.filter((m) => !m.is_deleted && !selectedIds.has(m.id))
  const name = (id: string) => {
    const m = memberById.get(id)
    return m ? `${m.first_name} ${m.last_name}` : "Unknown member"
  }

  return (
    <div className="space-y-2">
      <SectionTitle>Organizers</SectionTitle>
      <div className="flex flex-wrap gap-1.5 min-h-[2rem] items-center">
        {organizers.length === 0 && (
          <span className="text-sm text-muted-foreground">No organizers</span>
        )}
        {organizers.map((o) => (
          <Bubble
            key={o.id}
            label={name(o.member_id)}
            onRemove={() => removeOrganizer.mutate(o.member_id)}
          />
        ))}
      </div>
      {addable.length > 0 && (
        <AddCombobox
          triggerLabel="Add organizer…"
          placeholder="Search members…"
          emptyText="No members found."
          options={addable.map((m) => ({ id: m.id, label: `${m.first_name} ${m.last_name}` }))}
          onSelect={(id) => addOrganizer.mutate(id)}
        />
      )}
    </div>
  )
}
