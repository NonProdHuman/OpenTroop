import { useColors } from "@/lib/theme"
import { Pressable, Text, View } from "react-native"
import { useRouter } from "expo-router"
import { useAuth, useUser } from "@clerk/clerk-expo"
import { useActiveTenant } from "@/lib/tenant-context"
import { wipeAllLocalData } from "@/lib/local-wipe"
import { useSyncContext } from "@/lib/sync-context"
import { isAppLockEnabled, setAppLockEnabled } from "@/lib/app-lock"
import { disablePush, enablePush, getStoredPushToken } from "@/lib/push"
import { useCalendarSubscription } from "@/hooks/use-calendar"
import * as Clipboard from "expo-clipboard"
import { useEffect, useState } from "react"

function Row({ label, onPress, danger }: { label: string; onPress: () => void; danger?: boolean }) {
  const colors = useColors()
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => ({
        padding: 16,
        borderWidth: 1,
        borderColor: colors.borderLight,
        borderRadius: 12,
        marginBottom: 10,
        backgroundColor: pressed ? colors.hairline : colors.surface,
      })}
    >
      <Text style={{ fontSize: 15, fontWeight: "600", color: danger ? colors.danger : colors.textStrong }}>
        {label}
      </Text>
    </Pressable>
  )
}

export default function SettingsScreen() {
  const colors = useColors()
  const router = useRouter()
  const { signOut } = useAuth()
  const { user } = useUser()
  const { activeTenant, setActiveTenant } = useActiveTenant()
  const { failedCommands, lastOutcome, isSyncing, sync, http } = useSyncContext()
  const [lockEnabled, setLockEnabled] = useState(false)
  const [pushEnabled, setPushEnabled] = useState(false)
  const [pushError, setPushError] = useState<string | null>(null)
  const calendar = useCalendarSubscription()
  const [copied, setCopied] = useState(false)
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
      <Text style={{ color: colors.textMuted, marginBottom: 4 }}>Signed in as</Text>
      <Text style={{ fontSize: 16, fontWeight: "600", marginBottom: 16 }}>
        {user?.primaryEmailAddress?.emailAddress ?? "…"}
      </Text>
      <Text style={{ color: colors.textMuted, marginBottom: 4 }}>Troop</Text>
      <Text style={{ fontSize: 16, fontWeight: "600", marginBottom: 16 }}>
        {activeTenant?.tenant_name}
      </Text>

      <Row label="Switch troop" onPress={() => router.push("/select-troop")} />
      <Row
        label={calendar.busy ? "Working…" : "Subscribe to calendar"}
        onPress={() => void calendar.create()}
      />
      {calendar.url && (
        <View
          style={{
            padding: 12,
            marginBottom: 10,
            borderWidth: 1,
            borderColor: colors.borderLight,
            borderRadius: 12,
            gap: 8,
          }}
        >
          <Text style={{ fontSize: 12, color: colors.text }} numberOfLines={2}>
            {calendar.url}
          </Text>
          <View style={{ flexDirection: "row", gap: 16 }}>
            <Pressable
              onPress={() => {
                void Clipboard.setStringAsync(calendar.url ?? "")
                setCopied(true)
              }}
            >
              <Text style={{ color: colors.accent, fontWeight: "600" }}>
                {copied ? "Copied!" : "Copy link"}
              </Text>
            </Pressable>
            <Pressable
              onPress={() => {
                setCopied(false)
                void calendar.rotate()
              }}
            >
              <Text style={{ color: colors.textMuted }}>Get a fresh link</Text>
            </Pressable>
          </View>
        </View>
      )}
      {calendar.error && (
        <Text style={{ color: colors.warning, marginBottom: 10, fontSize: 13 }}>{calendar.error}</Text>
      )}
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
      {pushError && <Text style={{ color: colors.danger, marginTop: 8 }}>{pushError}</Text>}
      <Text style={{ color: colors.textSubtle, marginTop: "auto", textAlign: "center" }}>
        {lastOutcome?.error
          ? `Showing local data — last sync failed: ${lastOutcome.error}`
          : "Attendance/RSVP screens on the offline mirror and Face ID app lock arrive in M5 (GH-93)."}
      </Text>
    </View>
  )
}
