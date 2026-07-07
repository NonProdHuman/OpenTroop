import { useColors } from "@/lib/theme"
import { FlatList, Pressable, Text, View } from "react-native"
import { Stack } from "expo-router"
import { useSyncContext } from "@/lib/sync-context"
import type { PendingCommand } from "@/data/commands"

const KIND_LABELS: Record<PendingCommand["kind"], string> = {
  "event.set_attendance_taken": "Start attendance",
  "participant.update": "RSVP / attendance update",
  "participant.create": "Event signup",
}

/**
 * GH-153 §C3: terminal replay failures land here with the server's reason —
 * no silent loss. Discard is the only action; a retry is re-doing the change
 * in the UI (which enqueues a fresh command).
 */
export default function SyncIssuesScreen() {
  const colors = useColors()
  const { failedCommands, discard } = useSyncContext()

  return (
    <>
      <Stack.Screen options={{ headerShown: true, title: "Sync issues" }} />
      <FlatList
        contentContainerStyle={{ padding: 16 }}
        data={failedCommands}
        keyExtractor={(item) => item.id}
        ListEmptyComponent={
          <Text style={{ color: colors.textMuted }}>
            All caught up — every offline change has synced.
          </Text>
        }
        renderItem={({ item }) => (
          <View
            style={{
              padding: 14,
              borderWidth: 1,
              borderColor: colors.dangerBorder,
              borderRadius: 12,
              marginBottom: 10,
              backgroundColor: colors.dangerBg,
            }}
          >
            <Text style={{ fontWeight: "600", color: colors.textStrong }}>{KIND_LABELS[item.kind]}</Text>
            <Text style={{ color: colors.dangerStrong, marginTop: 4 }}>
              {item.last_error ?? "The server rejected this change."}
            </Text>
            <Text style={{ color: colors.textMuted, marginTop: 4, fontSize: 12 }}>
              Queued {new Date(item.created_at).toLocaleString()}
            </Text>
            <Pressable onPress={() => discard(item.id)} style={{ marginTop: 8 }}>
              <Text style={{ color: colors.danger, fontWeight: "600" }}>Discard change</Text>
            </Pressable>
          </View>
        )}
      />
    </>
  )
}
