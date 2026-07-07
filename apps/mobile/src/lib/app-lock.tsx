import { useColors } from "@/lib/theme"
import { useCallback, useEffect, useState, type ReactNode } from "react"
import { AppState, Pressable, Text, View } from "react-native"
import * as LocalAuthentication from "expo-local-authentication"
import * as SecureStore from "expo-secure-store"

const APP_LOCK_KEY = "opentroop.app-lock"

/**
 * Optional biometric/PIN app lock (GH-153 §C5) — off by default. The local
 * mirror carries medical and contact info, so `member:read` holders get a
 * one-time enable nudge (Settings). Uses the device's enrolled Face ID /
 * Touch ID / passcode via expo-local-authentication.
 */

export async function isAppLockEnabled(): Promise<boolean> {
  return (await SecureStore.getItemAsync(APP_LOCK_KEY)) === "true"
}

/** Enable requires passing a biometric check first; returns the new state. */
export async function setAppLockEnabled(enabled: boolean): Promise<boolean> {
  if (enabled) {
    const hardware = await LocalAuthentication.hasHardwareAsync()
    const enrolled = await LocalAuthentication.isEnrolledAsync()
    if (!hardware || !enrolled) return false
    const result = await LocalAuthentication.authenticateAsync({
      promptMessage: "Confirm to enable the app lock",
    })
    if (!result.success) return false
  }
  await SecureStore.setItemAsync(APP_LOCK_KEY, enabled ? "true" : "false")
  return enabled
}

export function AppLockGate({ children }: { children: ReactNode }) {
  const colors = useColors()
  // null = still reading the setting; keep rendering children (no flash) and
  // lock only once we know the lock is on.
  const [locked, setLocked] = useState<boolean | null>(null)

  const unlock = useCallback(async () => {
    const result = await LocalAuthentication.authenticateAsync({
      promptMessage: "Unlock OpenTroop",
    })
    if (result.success) setLocked(false)
  }, [])

  useEffect(() => {
    void isAppLockEnabled().then((enabled) => {
      setLocked(enabled)
      if (enabled) void unlock()
    })
  }, [unlock])

  // Re-lock when the app returns to the foreground.
  useEffect(() => {
    const sub = AppState.addEventListener("change", (state) => {
      if (state !== "active") return
      void isAppLockEnabled().then((enabled) => {
        if (enabled) {
          setLocked(true)
          void unlock()
        }
      })
    })
    return () => sub.remove()
  }, [unlock])

  if (locked) {
    return (
      <View
        style={{
          flex: 1,
          alignItems: "center",
          justifyContent: "center",
          gap: 16,
          backgroundColor: colors.background,
        }}
      >
        <Text style={{ fontSize: 22, fontWeight: "700", color: colors.textStrong }}>
          OpenTroop is locked
        </Text>
        <Pressable
          onPress={() => void unlock()}
          style={{
            backgroundColor: colors.brand,
            borderRadius: 8,
            paddingHorizontal: 20,
            paddingVertical: 12,
          }}
        >
          <Text style={{ color: colors.onBrand, fontWeight: "600" }}>Unlock with Face ID</Text>
        </Pressable>
      </View>
    )
  }
  return <>{children}</>
}
