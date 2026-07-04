import { useMemo } from "react"
import { FlatList, RefreshControl, Text, View } from "react-native"
import { useEvents } from "@/hooks/use-data"
import { formatEventStart, splitEventsByTime } from "@/lib/format"
import { LoadingScreen } from "@/components/loading-screen"
import type { Event } from "@/lib/types"

function EventRow({ event }: { event: Event }) {
  return (
    <View
      style={{
        padding: 14,
        borderWidth: 1,
        borderColor: "#e5e7eb",
        borderRadius: 12,
        marginBottom: 8,
        backgroundColor: "white",
      }}
    >
      <Text style={{ fontSize: 15, fontWeight: "600" }}>{event.name}</Text>
      <Text style={{ color: "#666", marginTop: 2 }}>
        {formatEventStart(event.scheduled_start, event.all_day)}
      </Text>
    </View>
  )
}

export default function EventsScreen() {
  const { data: events, isLoading, refetch, isRefetching, error } = useEvents()
  const sections = useMemo(
    () => splitEventsByTime(events ?? [], new Date()),
    [events],
  )

  if (isLoading) return <LoadingScreen />

  return (
    <FlatList
      contentContainerStyle={{ padding: 16 }}
      refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={() => refetch()} />}
      data={sections.upcoming}
      keyExtractor={(item) => item.id}
      renderItem={({ item }) => <EventRow event={item} />}
      ListHeaderComponent={
        error ? (
          <Text style={{ color: "#b91c1c", marginBottom: 12 }}>
            Couldn&apos;t load events — pull to retry. (Offline reads arrive with the sync
            layer.)
          </Text>
        ) : null
      }
      ListEmptyComponent={
        !error ? (
          <Text style={{ color: "#666" }}>No upcoming events.</Text>
        ) : null
      }
    />
  )
}
