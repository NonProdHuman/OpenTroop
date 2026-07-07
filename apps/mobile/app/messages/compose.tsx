import { useColors } from "@/lib/theme"
import { useMemo, useState } from "react"
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  Switch,
  Text,
  TextInput,
  useColorScheme,
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
  const colors = useColors()
  const scheme = useColorScheme()
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
        send_to_all: false,
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
            placeholderTextColor={colors.textSubtle}
            keyboardAppearance={scheme === "dark" ? "dark" : "light"}
            style={{
              borderWidth: 1,
              borderColor: colors.border,
              borderRadius: 8,
              padding: 12,
              fontSize: 16,
              color: colors.text,
              backgroundColor: colors.surface,
            }}
          />
          <TextInput
            value={body}
            onChangeText={setBody}
            placeholder="Write your message…"
            placeholderTextColor={colors.textSubtle}
            keyboardAppearance={scheme === "dark" ? "dark" : "light"}
            multiline
            style={{
              borderWidth: 1,
              borderColor: colors.border,
              borderRadius: 8,
              padding: 12,
              minHeight: 120,
              textAlignVertical: "top",
              color: colors.text,
              backgroundColor: colors.surface,
            }}
          />

          <Text style={{ fontWeight: "700", marginTop: 4, color: colors.textStrong }}>Send to</Text>
          {isLoading && <Text style={{ color: colors.textMuted }}>Loading groups…</Text>}
          {groupsError && (
            <Text style={{ color: colors.danger }}>
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
                      borderColor: isSelected ? colors.accent : colors.textSubtle,
                      backgroundColor: isSelected ? colors.brand : colors.surface,
                      alignItems: "center",
                      justifyContent: "center",
                    }}
                  >
                    {isSelected && <Text style={{ color: colors.onBrand, fontSize: 12 }}>✓</Text>}
                  </View>
                  <Text style={{ fontSize: 15, color: colors.text }}>{group.name}</Text>
                </Pressable>
                {target && (
                  <Pressable onPress={() => cycleAudience(group.id)}>
                    <Text style={{ color: colors.accent, fontSize: 12 }}>
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
              <Text style={{ color: colors.text }}>Email</Text>
            </View>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
              <Switch value={sendPush} onValueChange={setSendPush} />
              <Text style={{ color: colors.text }}>Push</Text>
            </View>
          </View>

          {error && <Text style={{ color: colors.danger }}>{error}</Text>}

          <Pressable
            disabled={!canSend}
            onPress={send}
            style={{
              backgroundColor: canSend ? colors.brand : colors.textSubtle,
              borderRadius: 10,
              padding: 14,
              alignItems: "center",
              marginTop: 4,
            }}
          >
            <Text style={{ color: colors.onBrand, fontWeight: "700" }}>
              {sending ? "Sending…" : "Send now"}
            </Text>
          </Pressable>
        </ScrollView>
      </KeyboardAvoidingView>
    </>
  )
}
