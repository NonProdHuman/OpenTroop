import { useColors } from "@/lib/theme"
import { FlatList, Pressable, Text, View } from "react-native"
import { Redirect, useRouter } from "expo-router"
import { useAuth } from "@clerk/clerk-expo"
import { useMemberships } from "@/hooks/use-data"
import { useActiveTenant } from "@/lib/tenant-context"
import { LoadingScreen } from "@/components/loading-screen"

export default function SelectTroopScreen() {
  const colors = useColors()
  const router = useRouter()
  const { isSignedIn, isLoaded } = useAuth()
  const { setActiveTenant } = useActiveTenant()
  const { data: memberships, isLoading, error, refetch, isRefetching } = useMemberships()

  if (!isLoaded) return <LoadingScreen />
  if (!isSignedIn) return <Redirect href="/sign-in" />
  if (isLoading) return <LoadingScreen />

  return (
    <View style={{ flex: 1, padding: 24, paddingTop: 80 }}>
      <Text style={{ fontSize: 22, fontWeight: "700", marginBottom: 16 }}>Choose your troop</Text>
      {error && (
        <Text style={{ color: colors.danger, marginBottom: 12 }}>
          Couldn&apos;t load your troops. Pull to retry or check your connection.
        </Text>
      )}
      {memberships?.length === 0 && (
        <Text style={{ color: colors.textMuted }}>
          Your account isn&apos;t linked to a troop yet. Ask a troop admin for an invite, then
          claim it on the web first.
        </Text>
      )}
      <FlatList
        data={memberships ?? []}
        keyExtractor={(item) => item.tenant_id}
        refreshing={isRefetching}
        onRefresh={() => void refetch()}
        // Let the pull gesture work even when the list is empty (error state).
        contentContainerStyle={{ flexGrow: 1 }}
        renderItem={({ item }) => (
          <Pressable
            onPress={() => {
              setActiveTenant(item)
              router.replace("/(tabs)/events")
            }}
            style={({ pressed }) => ({
              padding: 16,
              borderWidth: 1,
              borderColor: colors.borderLight,
              borderRadius: 12,
              marginBottom: 10,
              backgroundColor: pressed ? colors.hairline : colors.surface,
            })}
          >
            <Text style={{ fontSize: 16, fontWeight: "600" }}>{item.tenant_name}</Text>
            <Text style={{ color: colors.textMuted, marginTop: 2 }}>
              {item.tenant_slug}
              {item.is_admin ? " · admin" : ""}
            </Text>
          </Pressable>
        )}
      />
    </View>
  )
}
