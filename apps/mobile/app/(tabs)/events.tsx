import { colors } from "@/lib/theme"
import { useMemo } from "react"
import { FlatList, Pressable, RefreshControl, Text, View } from "react-native"
import { Link } from "expo-router"
import { useMirrorEvents } from "@/hooks/use-mirror"
import { useSyncContext } from "@/lib/sync-context"
import { formatEventStart, splitEventsByTime } from "@/lib/format"
import type { Event } from "@/lib/types"

function EventRow({ event }: { event: Event }) {
  return (
    <Link href={{ pathname: "/event/[id]", params: { id: event.id } }} asChild>
      <Pressable
        style={({ pressed }) => ({
          padding: 14,
          borderWidth: 1,
          borderColor: colors.borderLight,
          borderRadius: 12,
          marginBottom: 8,
          backgroundColor: pressed ? colors.hairline : "white",
        })}
      >
        <Text style={{ fontSize: 15, fontWeight: "600" }}>{event.name}</Text>
        <Text style={{ color: colors.textMuted, marginTop: 2 }}>
          {formatEventStart(event.scheduled_start, event.all_day)}
          {event.attendance_taken ? "  ·  attendance taken" : ""}
        </Text>
      </Pressable>
    </Link>
  )
}

export default function EventsScreen() {
  const events = useMirrorEvents()
  const { sync, isSyncing, lastOutcome } = useSyncContext()
  const sections = useMemo(() => splitEventsByTime(events, new Date()), [events])

  return (
    <FlatList
      contentContainerStyle={{ padding: 16 }}
      refreshControl={<RefreshControl refreshing={isSyncing} onRefresh={() => void sync()} />}
      data={sections.upcoming}
      keyExtractor={(item) => item.id}
      renderItem={({ item }) => <EventRow event={item} />}
      ListHeaderComponent={
        lastOutcome?.error && events.length === 0 ? (
          <Text style={{ color: colors.textMuted, marginBottom: 12 }}>
            Offline and nothing synced yet — connect once to mirror your troop&apos;s data.
          </Text>
        ) : null
      }
      ListFooterComponent={
        sections.past.length > 0 ? (
          <View style={{ marginTop: 16 }}>
            <Text style={{ color: colors.textMuted, fontWeight: "600", marginBottom: 8 }}>Past</Text>
            {sections.past.slice(0, 10).map((event) => (
              <EventRow key={event.id} event={event} />
            ))}
          </View>
        ) : null
      }
      ListEmptyComponent={
        !lastOutcome?.error ? <Text style={{ color: colors.textMuted }}>No upcoming events.</Text> : null
      }
    />
  )
}
