import { FlatList, Pressable, RefreshControl, Text } from "react-native"
import { Link } from "expo-router"
import { useMirrorMembers } from "@/hooks/use-mirror"
import { useSyncContext } from "@/lib/sync-context"
import { formatMemberName } from "@/lib/format"

export default function RosterScreen() {
  const members = useMirrorMembers()
  const { sync, isSyncing } = useSyncContext()

  return (
    <FlatList
      contentContainerStyle={{ padding: 16 }}
      refreshControl={<RefreshControl refreshing={isSyncing} onRefresh={() => void sync()} />}
      data={members}
      keyExtractor={(item) => item.id}
      renderItem={({ item }) => (
        <Link href={{ pathname: "/member/[id]", params: { id: item.id } }} asChild>
          <Pressable
            style={{ paddingVertical: 10, borderBottomWidth: 1, borderColor: "#f3f4f6" }}
          >
            <Text style={{ fontSize: 15 }}>
              {formatMemberName(item)}
              {item.member_type === "adult" ? "  ·  adult" : ""}
              {item.membership_status !== "active" ? `  ·  ${item.membership_status}` : ""}
            </Text>
          </Pressable>
        </Link>
      )}
      ListEmptyComponent={
        <Text style={{ color: "#666" }}>
          The roster mirrors for members with the member-read permission — your own
          family&apos;s records live in the web app for now.
        </Text>
      }
    />
  )
}
