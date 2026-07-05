import { Text, useColorScheme, View } from "react-native"
import { DarkTheme, DefaultTheme, Stack, ThemeProvider } from "expo-router"
import { StatusBar } from "expo-status-bar"
import { ClerkProvider } from "@clerk/clerk-expo"
import { tokenCache } from "@clerk/clerk-expo/token-cache"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { CLERK_PUBLISHABLE_KEY } from "@/lib/env"
import { IdentityGate } from "@/lib/identity-gate"
import { TenantProvider } from "@/lib/tenant-context"
import { SyncProvider } from "@/lib/sync-context"
import { AppLockGate } from "@/lib/app-lock"
import { useColors } from "@/lib/theme"

const queryClient = new QueryClient()

export default function RootLayout() {
  const colors = useColors()
  const scheme = useColorScheme()

  if (!CLERK_PUBLISHABLE_KEY) {
    return (
      <View
        style={{
          flex: 1,
          justifyContent: "center",
          padding: 24,
          backgroundColor: colors.background,
        }}
      >
        <Text style={{ fontSize: 16, fontWeight: "600", color: colors.textStrong }}>
          OpenTroop is not configured
        </Text>
        <Text style={{ marginTop: 8, color: colors.textMuted }}>
          Set EXPO_PUBLIC_CLERK_PUBLISHABLE_KEY in apps/mobile/.env (see .env.example) and
          restart the dev server.
        </Text>
      </View>
    )
  }

  // Theme React Navigation chrome (headers, tab bar, default screen backgrounds)
  // from the same palette the screens use, so everything flips together.
  const base = scheme === "dark" ? DarkTheme : DefaultTheme
  const navTheme: typeof DefaultTheme = {
    ...base,
    colors: {
      ...base.colors,
      background: colors.background,
      card: colors.surface,
      text: colors.textStrong,
      border: colors.hairline,
      primary: colors.accent,
      notification: colors.danger,
    },
  }

  return (
    <ClerkProvider publishableKey={CLERK_PUBLISHABLE_KEY} tokenCache={tokenCache}>
      <QueryClientProvider client={queryClient}>
        <IdentityGate>
          <TenantProvider>
            <SyncProvider>
              <AppLockGate>
                <ThemeProvider value={navTheme}>
                  <StatusBar style="auto" />
                  <Stack screenOptions={{ headerShown: false }} />
                </ThemeProvider>
              </AppLockGate>
            </SyncProvider>
          </TenantProvider>
        </IdentityGate>
      </QueryClientProvider>
    </ClerkProvider>
  )
}
