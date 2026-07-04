import { Pressable, ScrollView, Switch, Text, View } from "react-native"
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
  const { enqueue } = useSyncContext()
  const current = participant?.rsvp_status ?? "no_response"

  const setRsvp = (rsvp_status: string) => {
    // Existing row → field-granular update; none → signup with the reply.
    // Both queue offline and replay through the interactive API (GH-153 §C3).
    enqueue(participant ? "participant.update" : "participant.create", {
      event_id: eventId,
      member_id: member.id,
      rsvp_status,
    })
  }

  return (
    <View style={{ paddingVertical: 8, borderBottomWidth: 1, borderColor: "#f3f4f6" }}>
      <Text style={{ fontWeight: "600", marginBottom: 6 }}>{formatMemberName(member)}</Text>
      <View style={{ flexDirection: "row", gap: 8 }}>
        {RSVP_OPTIONS.map((option) => (
          <Pressable
            key={option.value}
            onPress={() => setRsvp(option.value)}
            style={{
              paddingHorizontal: 12,
              paddingVertical: 6,
              borderRadius: 999,
              borderWidth: 1,
              borderColor: current === option.value ? "#1d4ed8" : "#d1d5db",
              backgroundColor: current === option.value ? "#dbeafe" : "white",
            }}
          >
            <Text style={{ color: current === option.value ? "#1d4ed8" : "#374151" }}>
              {option.label}
            </Text>
          </Pressable>
        ))}
      </View>
    </View>
  )
}

export default function EventDetailScreen() {
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
        <Text style={{ padding: 24, color: "#666" }}>
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
          <Text style={{ color: "#666", marginTop: 4 }}>
            {formatEventStart(event.scheduled_start, event.all_day)}
          </Text>
          {event.location_notes ? (
            <Text style={{ color: "#666", marginTop: 2 }}>{event.location_notes}</Text>
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
                    backgroundColor: "#1d4ed8",
                    borderRadius: 8,
                    paddingHorizontal: 12,
                    paddingVertical: 8,
                  }}
                >
                  <Text style={{ color: "white", fontWeight: "600" }}>Take attendance</Text>
                </Pressable>
              )}
            </View>
            {event.attendance_taken ? (
              participants.length === 0 ? (
                <Text style={{ color: "#666" }}>No one on the list yet.</Text>
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
                      borderColor: "#f3f4f6",
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
              <Text style={{ color: "#666" }}>
                Start attendance to check people in — it works offline and syncs later.
              </Text>
            )}
          </View>
        )}
      </ScrollView>
    </>
  )
}
