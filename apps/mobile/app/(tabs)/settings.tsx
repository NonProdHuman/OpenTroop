import { Pressable, Text, View } from "react-native"
import { useRouter } from "expo-router"
import { useAuth, useUser } from "@clerk/clerk-expo"
import { useActiveTenant } from "@/lib/tenant-context"

function Row({ label, onPress, danger }: { label: string; onPress: () => void; danger?: boolean }) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => ({
        padding: 16,
        borderWidth: 1,
        borderColor: "#e5e7eb",
        borderRadius: 12,
        marginBottom: 10,
        backgroundColor: pressed ? "#f3f4f6" : "white",
      })}
    >
      <Text style={{ fontSize: 15, fontWeight: "600", color: danger ? "#b91c1c" : "#111" }}>
        {label}
      </Text>
    </Pressable>
  )
}

export default function SettingsScreen() {
  const router = useRouter()
  const { signOut } = useAuth()
  const { user } = useUser()
  const { activeTenant, setActiveTenant } = useActiveTenant()

  return (
    <View style={{ flex: 1, padding: 16 }}>
      <Text style={{ color: "#666", marginBottom: 4 }}>Signed in as</Text>
      <Text style={{ fontSize: 16, fontWeight: "600", marginBottom: 16 }}>
        {user?.primaryEmailAddress?.emailAddress ?? "…"}
      </Text>
      <Text style={{ color: "#666", marginBottom: 4 }}>Troop</Text>
      <Text style={{ fontSize: 16, fontWeight: "600", marginBottom: 16 }}>
        {activeTenant?.tenant_name}
      </Text>

      <Row label="Switch troop" onPress={() => router.push("/select-troop")} />
      <Row
        label="Sign out"
        danger
        onPress={() => {
          // GH-153 §C5: sign-out wipes local state. Today that's the tenant
          // selection; the M4 data layer adds tenant DB + outbox wipes here.
          setActiveTenant(null)
          void signOut()
        }}
      />
      <Text style={{ color: "#9ca3af", marginTop: "auto", textAlign: "center" }}>
        Offline sync, attendance, and Face ID app lock arrive in the next milestones (GH-93).
      </Text>
    </View>
  )
}
