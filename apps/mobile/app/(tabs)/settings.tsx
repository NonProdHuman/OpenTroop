import { Pressable, Text, View } from "react-native"
import { useRouter } from "expo-router"
import { useAuth, useUser } from "@clerk/clerk-expo"
import { useActiveTenant } from "@/lib/tenant-context"
import { wipeAllLocalData } from "@/lib/local-wipe"
import { useSyncContext } from "@/lib/sync-context"
import { isAppLockEnabled, setAppLockEnabled } from "@/lib/app-lock"
import { disablePush, enablePush, getStoredPushToken } from "@/lib/push"
import { useEffect, useState } from "react"

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
  const { failedCommands, lastOutcome, isSyncing, sync, http } = useSyncContext()
  const [lockEnabled, setLockEnabled] = useState(false)
  const [pushEnabled, setPushEnabled] = useState(false)
  const [pushError, setPushError] = useState<string | null>(null)
  useEffect(() => {
    void isAppLockEnabled().then(setLockEnabled)
    void getStoredPushToken().then((token) => setPushEnabled(Boolean(token)))
  }, [])

  const togglePush = async () => {
    setPushError(null)
    try {
      if (pushEnabled) {
        await disablePush(http)
        setPushEnabled(false)
      } else if (http) {
        await enablePush(http)
        setPushEnabled(true)
      }
    } catch (error) {
      setPushError(error instanceof Error ? error.message : "Could not enable notifications.")
    }
  }

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
        label={isSyncing ? "Syncing…" : "Sync now"}
        onPress={() => {
          void sync()
        }}
      />
      <Row
        label={
          failedCommands.length > 0
            ? `Sync issues (${failedCommands.length})`
            : "Sync issues"
        }
        onPress={() => router.push("/sync-issues")}
      />
      <Row
        label={pushEnabled ? "Notifications: on" : "Notifications: off"}
        onPress={() => {
          void togglePush()
        }}
      />
      <Row
        label={lockEnabled ? "App lock: on (Face ID)" : "App lock: off"}
        onPress={() => {
          void setAppLockEnabled(!lockEnabled).then(setLockEnabled)
        }}
      />
      <Row
        label="Sign out"
        danger
        onPress={() => {
          // GH-153 §C5: local data belongs to the identity — wipe every
          // tenant database and queue before dropping the session.
          void disablePush(http)
            .catch(() => undefined)
            .then(() => wipeAllLocalData())
            .finally(() => {
              setActiveTenant(null)
              void signOut()
            })
        }}
      />
      {pushError && <Text style={{ color: "#b91c1c", marginTop: 8 }}>{pushError}</Text>}
      <Text style={{ color: "#9ca3af", marginTop: "auto", textAlign: "center" }}>
        {lastOutcome?.error
          ? "Offline — showing local data; changes will sync when you're back."
          : "Attendance/RSVP screens on the offline mirror and Face ID app lock arrive in M5 (GH-93)."}
      </Text>
    </View>
  )
}
