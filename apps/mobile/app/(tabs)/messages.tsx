import { useColors } from "@/lib/theme"
import { useState } from "react"
import { FlatList, Pressable, Text, View } from "react-native"
import { Link } from "expo-router"
import { useInbox, useMarkInboxRead, type InboxItem } from "@/hooks/use-inbox"
import { useCachedPermissions } from "@/hooks/use-mirror"
import { useSyncContext } from "@/lib/sync-context"

function formatSent(iso: string | null): string {
  if (!iso) return ""
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })
}

function InboxRow({ item }: { item: InboxItem }) {
  const colors = useColors()
  const [open, setOpen] = useState(false)
  const markRead = useMarkInboxRead()
  const unread = item.readAt === null

  return (
    <Pressable
      onPress={() => {
        setOpen((o) => !o)
        if (unread) markRead(item.recipientId)
      }}
      style={{ paddingVertical: 12, paddingHorizontal: 16, borderBottomWidth: 1, borderColor: colors.hairline }}
    >
      <View style={{ flexDirection: "row", justifyContent: "space-between", gap: 8 }}>
        <Text style={{ flex: 1, fontSize: 15, fontWeight: unread ? "700" : "500" }} numberOfLines={1}>
          {unread ? "• " : ""}
          {item.subject}
        </Text>
        <Text style={{ color: colors.textSubtle, fontSize: 11 }}>{formatSent(item.sentAt)}</Text>
      </View>
      <Text
        style={{ color: colors.textSecondary, fontSize: 13, marginTop: 2 }}
        numberOfLines={open ? undefined : 1}
      >
        {item.body}
      </Text>
    </Pressable>
  )
}

export default function MessagesScreen() {
  const colors = useColors()
  const { items, unreadCount } = useInbox()
  const { sync, isSyncing } = useSyncContext()
  const { has } = useCachedPermissions()
  const canSend = has("communication:send_troop")

  return (
    <View style={{ flex: 1 }}>
      {canSend && (
        <Link href="/messages/compose" asChild>
          <Pressable
            style={{
              margin: 16,
              marginBottom: 8,
              backgroundColor: colors.brand,
              borderRadius: 10,
              padding: 12,
              alignItems: "center",
            }}
          >
            <Text style={{ color: colors.onBrand, fontWeight: "600" }}>New announcement</Text>
          </Pressable>
        </Link>
      )}
      <FlatList
        data={items}
        keyExtractor={(item) => item.recipientId}
        onRefresh={() => void sync()}
        refreshing={isSyncing}
        renderItem={({ item }) => <InboxRow item={item} />}
        ListHeaderComponent={
          unreadCount > 0 ? (
            <Text style={{ color: colors.textMuted, fontSize: 12, paddingHorizontal: 16, paddingTop: 8 }}>
              {unreadCount} unread
            </Text>
          ) : null
        }
        ListEmptyComponent={
          <Text style={{ color: colors.textMuted, padding: 24 }}>
            No messages yet. Troop announcements will appear here.
          </Text>
        }
      />
    </View>
  )
}
