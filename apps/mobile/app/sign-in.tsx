import { useColors } from "@/lib/theme"
import { useState } from "react"
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  Text,
  TextInput,
} from "react-native"
import { useRouter } from "expo-router"
import { useSignIn } from "@clerk/clerk-expo"

/**
 * Email + password sign-in against the shared Clerk instance. OAuth/SSO flows
 * (Google, Apple) come later; this matches the web dev/e2e account style.
 */
export default function SignInScreen() {
  const colors = useColors()
  const router = useRouter()
  const { signIn, setActive, isLoaded } = useSignIn()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const onSubmit = async () => {
    if (!isLoaded || submitting) return
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
        disabled={submitting || !email || !password}
        style={({ pressed }) => ({
          backgroundColor: submitting || !email || !password ? colors.textSubtle : colors.brand,
          opacity: pressed ? 0.8 : 1,
          borderRadius: 8,
          padding: 14,
          alignItems: "center",
        })}
      >
        <Text style={{ color: colors.onBrand, fontWeight: "600" }}>
          {submitting ? "Signing in…" : "Sign in"}
        </Text>
      </Pressable>
    </KeyboardAvoidingView>
  )
}
