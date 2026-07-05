import { useMemo, useState } from "react"
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  Switch,
  Text,
  TextInput,
  View,
} from "react-native"
import { Stack, useRouter } from "expo-router"
import { useComposeAndSend, useGroupsOnline } from "@/hooks/use-messaging"
import type { AudienceType, Group } from "@/lib/types"

const AUDIENCE_CYCLE: AudienceType[] = ["members", "members_and_parents", "parents_only"]
const AUDIENCE_LABELS: Record<AudienceType, string> = {
  members: "Members",
  members_and_parents: "Members + Parents",
  parents_only: "Parents only",
}

type Target = { group_id: string; audience_type: AudienceType }

export default function ComposeScreen() {
  const router = useRouter()
  const { data: groups = [], isLoading, error: groupsError } = useGroupsOnline(true)
  const composeAndSend = useComposeAndSend()

  const [subject, setSubject] = useState("")
  const [body, setBody] = useState("")
  const [sendEmail, setSendEmail] = useState(true)
  const [sendPush, setSendPush] = useState(true)
  const [targets, setTargets] = useState<Target[]>([])
  const [error, setError] = useState<string | null>(null)
  const [sending, setSending] = useState(false)

  const selected = useMemo(() => new Set(targets.map((t) => t.group_id)), [targets])
  const canSend = subject.trim() && body.trim() && targets.length > 0 && !sending

  const toggleGroup = (group: Group) => {
    setTargets((prev) =>
      prev.some((t) => t.group_id === group.id)
        ? prev.filter((t) => t.group_id !== group.id)
        : [...prev, { group_id: group.id, audience_type: "members" }],
    )
  }
  const cycleAudience = (groupId: string) => {
    setTargets((prev) =>
      prev.map((t) => {
        if (t.group_id !== groupId) return t
        const next = AUDIENCE_CYCLE[(AUDIENCE_CYCLE.indexOf(t.audience_type) + 1) % 3]
        return { ...t, audience_type: next }
      }),
    )
  }

  const send = async () => {
    setSending(true)
    setError(null)
    try {
      await composeAndSend({
        subject,
        body,
        send_email: sendEmail,
        send_push: sendPush,
        group_targets: targets,
        scheduled_at: null,
      })
      router.back()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not send the announcement.")
    } finally {
      setSending(false)
    }
  }

  return (
    <>
      <Stack.Screen options={{ headerShown: true, title: "New announcement" }} />
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        <ScrollView contentContainerStyle={{ padding: 16, gap: 12 }}>
          <TextInput
            value={subject}
            onChangeText={setSubject}
            placeholder="Subject"
            style={{ borderWidth: 1, borderColor: "#d1d5db", borderRadius: 8, padding: 12, fontSize: 16 }}
          />
          <TextInput
            value={body}
            onChangeText={setBody}
            placeholder="Write your message…"
            multiline
            style={{
              borderWidth: 1,
              borderColor: "#d1d5db",
              borderRadius: 8,
              padding: 12,
              minHeight: 120,
              textAlignVertical: "top",
            }}
          />

          <Text style={{ fontWeight: "700", marginTop: 4 }}>Send to</Text>
          {isLoading && <Text style={{ color: "#666" }}>Loading groups…</Text>}
          {groupsError && (
            <Text style={{ color: "#b91c1c" }}>
              Composing needs a connection to load groups.
            </Text>
          )}
          {groups.map((group) => {
            const target = targets.find((t) => t.group_id === group.id)
            const isSelected = selected.has(group.id)
            return (
              <View
                key={group.id}
                style={{ flexDirection: "row", alignItems: "center", gap: 8 }}
              >
                <Pressable
                  onPress={() => toggleGroup(group)}
                  style={{ flex: 1, flexDirection: "row", alignItems: "center", gap: 8 }}
                >
                  <View
                    style={{
                      width: 20,
                      height: 20,
                      borderRadius: 4,
                      borderWidth: 1,
                      borderColor: isSelected ? "#1d4ed8" : "#9ca3af",
                      backgroundColor: isSelected ? "#1d4ed8" : "white",
                      alignItems: "center",
                      justifyContent: "center",
                    }}
                  >
                    {isSelected && <Text style={{ color: "white", fontSize: 12 }}>✓</Text>}
                  </View>
                  <Text style={{ fontSize: 15 }}>{group.name}</Text>
                </Pressable>
                {target && (
                  <Pressable onPress={() => cycleAudience(group.id)}>
                    <Text style={{ color: "#1d4ed8", fontSize: 12 }}>
                      {AUDIENCE_LABELS[target.audience_type]} ▸
                    </Text>
                  </Pressable>
                )}
              </View>
            )
          })}

          <View style={{ flexDirection: "row", alignItems: "center", gap: 12, marginTop: 8 }}>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
              <Switch value={sendEmail} onValueChange={setSendEmail} />
              <Text>Email</Text>
            </View>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
              <Switch value={sendPush} onValueChange={setSendPush} />
              <Text>Push</Text>
            </View>
          </View>

          {error && <Text style={{ color: "#b91c1c" }}>{error}</Text>}

          <Pressable
            disabled={!canSend}
            onPress={send}
            style={{
              backgroundColor: canSend ? "#1d4ed8" : "#9ca3af",
              borderRadius: 10,
              padding: 14,
              alignItems: "center",
              marginTop: 4,
            }}
          >
            <Text style={{ color: "white", fontWeight: "700" }}>
              {sending ? "Sending…" : "Send now"}
            </Text>
          </Pressable>
        </ScrollView>
      </KeyboardAvoidingView>
    </>
  )
}
