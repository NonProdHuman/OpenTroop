import { useColors } from "@/lib/theme"
import { useState } from "react"
import { Pressable, ScrollView, Switch, Text, TextInput, View } from "react-native"
import { Stack, useLocalSearchParams } from "expo-router"
import {
  useCachedPermissions,
  useMirrorEvent,
  useMirrorFamily,
  useMirrorMembers,
  useMirrorParticipants,
} from "@/hooks/use-mirror"
import { useSyncContext } from "@/lib/sync-context"
import { formatEventStart, formatMemberName } from "@/lib/format"
import type { EventParticipant, Member } from "@/lib/types"

const RSVP_OPTIONS = [
  { value: "going", label: "Going" },
  { value: "maybe", label: "Maybe" },
  { value: "declined", label: "Declined" },
] as const

function RsvpRow({
  member,
  participant,
  eventId,
}: {
  member: Member
  participant: EventParticipant | undefined
  eventId: string
}) {
  const colors = useColors()
  const { enqueue } = useSyncContext()
  const [expanded, setExpanded] = useState(false)
  const current = participant?.rsvp_status ?? "no_response"

  // Field-granular update on an existing row; signup+reply otherwise. Extra
  // RSVP details (driver/guests/note) coalesce into the same queued command.
  const patch = (fields: Record<string, unknown>) => {
    enqueue(participant ? "participant.update" : "participant.create", {
      event_id: eventId,
      member_id: member.id,
      ...fields,
    })
  }

  return (
    <View style={{ paddingVertical: 8, borderBottomWidth: 1, borderColor: colors.hairline }}>
      <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
        <Text style={{ fontWeight: "600", marginBottom: 6 }}>{formatMemberName(member)}</Text>
        <Pressable onPress={() => setExpanded((e) => !e)}>
          <Text style={{ color: colors.textMuted, fontSize: 12 }}>{expanded ? "Less" : "Details"}</Text>
        </Pressable>
      </View>
      <View style={{ flexDirection: "row", gap: 8 }}>
        {RSVP_OPTIONS.map((option) => (
          <Pressable
            key={option.value}
            onPress={() => patch({ rsvp_status: option.value })}
            style={{
              paddingHorizontal: 12,
              paddingVertical: 6,
              borderRadius: 999,
              borderWidth: 1,
              borderColor: current === option.value ? colors.accent : colors.border,
              backgroundColor: current === option.value ? colors.accentTint : colors.surface,
            }}
          >
            <Text style={{ color: current === option.value ? colors.accent : colors.text }}>
              {option.label}
            </Text>
          </Pressable>
        ))}
      </View>

      {expanded && (
        <View style={{ gap: 8, marginTop: 10 }}>
          <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}>
            <Text style={{ color: colors.text }}>Can drive</Text>
            <Switch
              value={participant?.driver === true}
              onValueChange={(driver) => patch({ driver })}
            />
          </View>
          <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}>
            <Text style={{ color: colors.text }}>Extra guests</Text>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 12 }}>
              <Pressable
                onPress={() => patch({ guest_count: Math.max(0, (participant?.guest_count ?? 0) - 1) })}
              >
                <Text style={{ fontSize: 20, color: colors.accent }}>−</Text>
              </Pressable>
              <Text style={{ minWidth: 20, textAlign: "center" }}>
                {participant?.guest_count ?? 0}
              </Text>
              <Pressable onPress={() => patch({ guest_count: (participant?.guest_count ?? 0) + 1 })}>
                <Text style={{ fontSize: 20, color: colors.accent }}>+</Text>
              </Pressable>
            </View>
          </View>
          <TextInput
            defaultValue={participant?.comment ?? ""}
            onEndEditing={(e) => patch({ comment: e.nativeEvent.text })}
            placeholder="Note for the organizer…"
            style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 8, padding: 8 }}
          />
        </View>
      )}
    </View>
  )
}

export default function EventDetailScreen() {
  const colors = useColors()
  const { id } = useLocalSearchParams<{ id: string }>()
  const event = useMirrorEvent(id)
  const participants = useMirrorParticipants(id)
  const family = useMirrorFamily()
  const members = useMirrorMembers()
  const { has } = useCachedPermissions()
  const { enqueue } = useSyncContext()

  if (!event) {
    return (
      <>
        <Stack.Screen options={{ headerShown: true, title: "Event" }} />
        <Text style={{ padding: 24, color: colors.textMuted }}>
          This event isn&apos;t in your local data yet — sync when you have signal.
        </Text>
      </>
    )
  }

  const memberName = (memberId: string) => {
    const member = members.find((m) => m.id === memberId)
    return member ? formatMemberName(member) : "Member"
  }
  const byMember = new Map(participants.map((p) => [p.member_id, p]))
  const canTakeAttendance = has("event:manage_attendance")
  const going = participants.filter((p) => p.rsvp_status === "going")

  return (
    <>
      <Stack.Screen options={{ headerShown: true, title: event.name }} />
      <ScrollView contentContainerStyle={{ padding: 16, gap: 20 }}>
        <View>
          <Text style={{ fontSize: 20, fontWeight: "700" }}>{event.name}</Text>
          <Text style={{ color: colors.textMuted, marginTop: 4 }}>
            {formatEventStart(event.scheduled_start, event.all_day)}
          </Text>
          {event.location_notes ? (
            <Text style={{ color: colors.textMuted, marginTop: 2 }}>{event.location_notes}</Text>
          ) : null}
          {event.description ? <Text style={{ marginTop: 8 }}>{event.description}</Text> : null}
        </View>

        {family.length > 0 && (
          <View>
            <Text style={{ fontSize: 16, fontWeight: "700", marginBottom: 4 }}>RSVP</Text>
            {family.map((member) => (
              <RsvpRow
                key={member.id}
                member={member}
                participant={byMember.get(member.id)}
                eventId={event.id}
              />
            ))}
          </View>
        )}

        {canTakeAttendance && (
          <View>
            <View
              style={{
                flexDirection: "row",
                alignItems: "center",
                justifyContent: "space-between",
                marginBottom: 4,
              }}
            >
              <Text style={{ fontSize: 16, fontWeight: "700" }}>
                Attendance ({going.length} going)
              </Text>
              {!event.attendance_taken && (
                <Pressable
                  onPress={() =>
                    enqueue("event.set_attendance_taken", {
                      event_id: event.id,
                      attendance_taken: true,
                    })
                  }
                  style={{
                    backgroundColor: colors.brand,
                    borderRadius: 8,
                    paddingHorizontal: 12,
                    paddingVertical: 8,
                  }}
                >
                  <Text style={{ color: colors.onBrand, fontWeight: "600" }}>Take attendance</Text>
                </Pressable>
              )}
            </View>
            {event.attendance_taken ? (
              participants.length === 0 ? (
                <Text style={{ color: colors.textMuted }}>No one on the list yet.</Text>
              ) : (
                participants.map((participant) => (
                  <View
                    key={participant.id}
                    style={{
                      flexDirection: "row",
                      alignItems: "center",
                      justifyContent: "space-between",
                      paddingVertical: 6,
                      borderBottomWidth: 1,
                      borderColor: colors.hairline,
                    }}
                  >
                    <Text>{memberName(participant.member_id)}</Text>
                    <Switch
                      value={participant.attended === true}
                      onValueChange={(attended) =>
                        // The 409 gate (attendance not started) is enforced
                        // server-side at replay; FIFO keeps the gate first.
                        enqueue("participant.update", {
                          event_id: event.id,
                          member_id: participant.member_id,
                          attended,
                        })
                      }
                    />
                  </View>
                ))
              )
            ) : (
              <Text style={{ color: colors.textMuted }}>
                Start attendance to check people in — it works offline and syncs later.
              </Text>
            )}
          </View>
        )}
      </ScrollView>
    </>
  )
}
