import { FlatList, RefreshControl, Text } from "react-native"
import { useMembers } from "@/hooks/use-data"
import { ApiError } from "@/lib/api"
import { formatMemberName } from "@/lib/format"
import { LoadingScreen } from "@/components/loading-screen"

export default function RosterScreen() {
  const { data: members, isLoading, refetch, isRefetching, error } = useMembers()

  if (isLoading) return <LoadingScreen />
  if (error instanceof ApiError && error.status === 403) {
    return (
      <Text style={{ padding: 24, color: "#666" }}>
        The roster requires the member-read permission. Your own family&apos;s info lives in
        the web app for now.
      </Text>
    )
  }

  const sorted = [...(members ?? [])].sort((a, b) =>
    `${a.last_name}${a.first_name}`.localeCompare(`${b.last_name}${b.first_name}`),
  )

  return (
    <FlatList
      contentContainerStyle={{ padding: 16 }}
      refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={() => refetch()} />}
      data={sorted}
      keyExtractor={(item) => item.id}
      renderItem={({ item }) => (
        <Text style={{ paddingVertical: 10, fontSize: 15, borderBottomWidth: 1, borderColor: "#f3f4f6" }}>
          {formatMemberName(item)}
          {item.member_type === "adult" ? "  ·  adult" : ""}
        </Text>
      )}
      ListEmptyComponent={<Text style={{ color: "#666" }}>No members yet.</Text>}
    />
  )
}
