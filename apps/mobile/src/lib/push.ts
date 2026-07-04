import * as Device from "expo-device"
import * as Notifications from "expo-notifications"
import * as SecureStore from "expo-secure-store"
import Constants from "expo-constants"
import { Platform } from "react-native"
import type { HttpClient } from "@/data/commands"

const PUSH_TOKEN_KEY = "opentroop.push-token"

/**
 * Push registration (GH-82). Opt-in from Settings — no auto-prompt on first
 * launch. The Expo push token registers against the *active tenant*; the
 * backend fans event notifications out to every registered device.
 */

export async function getStoredPushToken(): Promise<string | null> {
  return SecureStore.getItemAsync(PUSH_TOKEN_KEY)
}

async function fetchExpoPushToken(): Promise<string> {
  if (!Device.isDevice) {
    throw new Error("Push notifications need a physical device.")
  }
  const permission = await Notifications.requestPermissionsAsync()
  if (permission.status !== "granted") {
    throw new Error("Notification permission was declined.")
  }
  const projectId: string | undefined =
    Constants.easConfig?.projectId ?? Constants.expoConfig?.extra?.eas?.projectId
  const token = await Notifications.getExpoPushTokenAsync(
    projectId ? { projectId } : undefined,
  )
  return token.data
}

/** Enable: OS permission → Expo token → register with the active tenant. */
export async function enablePush(http: HttpClient): Promise<void> {
  const token = await fetchExpoPushToken()
  const response = await http("/notifications/push-tokens", {
    method: "POST",
    body: { token, platform: Platform.OS },
  })
  if (response.status >= 400) {
    throw new Error(`Push registration failed (HTTP ${response.status})`)
  }
  await SecureStore.setItemAsync(PUSH_TOKEN_KEY, token)
}

/** Disable / sign-out cleanup: best-effort server delete, always local clear. */
export async function disablePush(http: HttpClient | null): Promise<void> {
  const token = await getStoredPushToken()
  if (token && http) {
    try {
      await http("/notifications/push-tokens", { method: "DELETE", body: { token } })
    } catch {
      // Offline sign-out: the server prunes the token when it goes dead.
    }
  }
  await SecureStore.deleteItemAsync(PUSH_TOKEN_KEY)
}

/** Re-register the stored token after a troop switch (each tenant has its own row). */
export async function reregisterPushIfEnabled(http: HttpClient): Promise<void> {
  const token = await getStoredPushToken()
  if (!token) return
  try {
    await http("/notifications/push-tokens", {
      method: "POST",
      body: { token, platform: Platform.OS },
    })
  } catch {
    // Best-effort; the next explicit enable fixes a failed registration.
  }
}
