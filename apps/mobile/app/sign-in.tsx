import { useColors } from "@/lib/theme"
import { SSO_PROVIDERS, settleSsoFlow, type SsoStrategy } from "@/lib/sso"
import { useEffect, useState } from "react"
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  Text,
  TextInput,
  View,
} from "react-native"
import { useRouter } from "expo-router"
import { useSignIn, useSSO } from "@clerk/clerk-expo"
import * as AuthSession from "expo-auth-session"
import * as WebBrowser from "expo-web-browser"

// Closes the auth browser tab if the app was re-opened by the SSO redirect.
WebBrowser.maybeCompleteAuthSession()

/**
 * Sign-in: SSO first (Microsoft, Google — the same Clerk instance and provider
 * set as the web app's chooser; see src/lib/sso.ts, incl. the Apple/App Store
 * note), with email + password below as the fallback for password-strategy
 * accounts (dev/e2e style). SSO opens the system browser via Clerk's
 * `useSSO()` and returns on the `opentroop` scheme.
 */
export default function SignInScreen() {
  const colors = useColors()
  const router = useRouter()
  const { signIn, setActive, isLoaded } = useSignIn()
  const { startSSOFlow } = useSSO()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [ssoPending, setSsoPending] = useState<SsoStrategy | null>(null)

  // Android: pre-warm the custom tab so the SSO browser opens instantly.
  useEffect(() => {
    void WebBrowser.warmUpAsync()
    return () => {
      void WebBrowser.coolDownAsync()
    }
  }, [])

  const busy = submitting || ssoPending !== null

  const onSSO = async (strategy: SsoStrategy) => {
    if (busy) return
    setSsoPending(strategy)
    setError(null)
    try {
      const result = await startSSOFlow({
        strategy,
        redirectUrl: AuthSession.makeRedirectUri({ scheme: "opentroop", path: "sso-callback" }),
      })
      if (await settleSsoFlow(result)) {
        router.replace("/")
      } else {
        setError("Additional verification required — sign in on the web first.")
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Sign-in failed. Please try again."
      setError(message)
    } finally {
      setSsoPending(null)
    }
  }

  const onSubmit = async () => {
    if (!isLoaded || busy) return
    setSubmitting(true)
    setError(null)
    try {
      const attempt = await signIn.create({ identifier: email.trim(), password })
      if (attempt.status === "complete") {
        await setActive({ session: attempt.createdSessionId })
        router.replace("/")
      } else {
        setError("Additional verification required — sign in on the web first.")
      }
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Sign-in failed. Check your email and password."
      setError(message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === "ios" ? "padding" : undefined}
      style={{ flex: 1, justifyContent: "center", padding: 24, gap: 12 }}
    >
      <Text style={{ fontSize: 28, fontWeight: "700", marginBottom: 8 }}>OpenTroop</Text>

      {SSO_PROVIDERS.map(({ strategy, label }) => (
        <Pressable
          key={strategy}
          onPress={() => onSSO(strategy)}
          disabled={busy}
          style={({ pressed }) => ({
            backgroundColor: busy ? colors.textSubtle : colors.brand,
            opacity: pressed ? 0.8 : 1,
            borderRadius: 8,
            padding: 14,
            alignItems: "center",
          })}
        >
          <Text style={{ color: colors.onBrand, fontWeight: "600" }}>
            {ssoPending === strategy ? "Opening browser…" : label}
          </Text>
        </Pressable>
      ))}

      <View style={{ flexDirection: "row", alignItems: "center", gap: 8, marginVertical: 4 }}>
        <View style={{ flex: 1, height: 1, backgroundColor: colors.border }} />
        <Text style={{ color: colors.textSubtle, fontSize: 12 }}>or continue with email</Text>
        <View style={{ flex: 1, height: 1, backgroundColor: colors.border }} />
      </View>

      <TextInput
        placeholder="Email"
        autoCapitalize="none"
        autoComplete="email"
        keyboardType="email-address"
        value={email}
        onChangeText={setEmail}
        style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 8, padding: 12 }}
      />
      <TextInput
        placeholder="Password"
        secureTextEntry
        autoComplete="current-password"
        value={password}
        onChangeText={setPassword}
        style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 8, padding: 12 }}
      />
      {error && <Text style={{ color: colors.danger }}>{error}</Text>}
      <Pressable
        onPress={onSubmit}
        disabled={busy || !email || !password}
        style={({ pressed }) => ({
          backgroundColor: busy || !email || !password ? colors.textSubtle : colors.surface,
          borderWidth: 1,
          borderColor: colors.border,
          opacity: pressed ? 0.8 : 1,
          borderRadius: 8,
          padding: 14,
          alignItems: "center",
        })}
      >
        <Text style={{ color: colors.textStrong, fontWeight: "600" }}>
          {submitting ? "Signing in…" : "Sign in with email"}
        </Text>
      </Pressable>
    </KeyboardAvoidingView>
  )
}
