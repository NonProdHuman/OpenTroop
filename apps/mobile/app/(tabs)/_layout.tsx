import { Text } from "react-native"
import { Redirect, Tabs } from "expo-router"
import { useAuth } from "@clerk/clerk-expo"
import { useActiveTenant } from "@/lib/tenant-context"
import { LoadingScreen } from "@/components/loading-screen"

function TabIcon({ glyph }: { glyph: string }) {
  // Placeholder glyph icons; expo-symbols / vector icons land with the design pass.
  return <Text style={{ fontSize: 18 }}>{glyph}</Text>
}

export default function TabsLayout() {
  const { isLoaded, isSignedIn } = useAuth()
  const { activeTenant, isHydrated } = useActiveTenant()

  if (!isLoaded || !isHydrated) return <LoadingScreen />
  if (!isSignedIn) return <Redirect href="/sign-in" />
  if (!activeTenant) return <Redirect href="/select-troop" />

  return (
    <Tabs screenOptions={{ headerTitleAlign: "center" }}>
      <Tabs.Screen
        name="events"
        options={{
          title: "Events",
          headerTitle: activeTenant.tenant_name,
          tabBarIcon: () => <TabIcon glyph="📅" />,
        }}
      />
      <Tabs.Screen
        name="messages"
        options={{
          title: "Messages",
          headerTitle: activeTenant.tenant_name,
          tabBarIcon: () => <TabIcon glyph="📨" />,
        }}
      />
      <Tabs.Screen
        name="roster"
        options={{
          title: "Roster",
          headerTitle: activeTenant.tenant_name,
          tabBarIcon: () => <TabIcon glyph="👥" />,
        }}
      />
      <Tabs.Screen
        name="advancement"
        options={{
          title: "Advancement",
          headerTitle: activeTenant.tenant_name,
          tabBarIcon: () => <TabIcon glyph="⭐" />,
        }}
      />
      <Tabs.Screen
        name="settings"
        options={{ title: "Settings", tabBarIcon: () => <TabIcon glyph="⚙️" /> }}
      />
    </Tabs>
  )
}
