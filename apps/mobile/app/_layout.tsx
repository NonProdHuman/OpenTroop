import { Text, View } from "react-native"
import { Stack } from "expo-router"
import { StatusBar } from "expo-status-bar"
import { ClerkProvider } from "@clerk/clerk-expo"
import { tokenCache } from "@clerk/clerk-expo/token-cache"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { CLERK_PUBLISHABLE_KEY } from "@/lib/env"
import { TenantProvider } from "@/lib/tenant-context"
import { SyncProvider } from "@/lib/sync-context"
import { AppLockGate } from "@/lib/app-lock"

const queryClient = new QueryClient()

export default function RootLayout() {
  if (!CLERK_PUBLISHABLE_KEY) {
    return (
      <View style={{ flex: 1, justifyContent: "center", padding: 24 }}>
        <Text style={{ fontSize: 16, fontWeight: "600" }}>OpenTroop is not configured</Text>
        <Text style={{ marginTop: 8, color: "#666" }}>
          Set EXPO_PUBLIC_CLERK_PUBLISHABLE_KEY in apps/mobile/.env (see .env.example) and
          restart the dev server.
        </Text>
      </View>
    )
  }

  return (
    <ClerkProvider publishableKey={CLERK_PUBLISHABLE_KEY} tokenCache={tokenCache}>
      <QueryClientProvider client={queryClient}>
        <TenantProvider>
          <SyncProvider>
            <AppLockGate>
              <StatusBar style="auto" />
              <Stack screenOptions={{ headerShown: false }} />
            </AppLockGate>
          </SyncProvider>
        </TenantProvider>
      </QueryClientProvider>
    </ClerkProvider>
  )
}
