import { Redirect } from "expo-router"
import { useAuth } from "@clerk/clerk-expo"
import { useActiveTenant } from "@/lib/tenant-context"
import { LoadingScreen } from "@/components/loading-screen"

export default function Index() {
  const { isLoaded, isSignedIn } = useAuth()
  const { activeTenant, isHydrated } = useActiveTenant()

  if (!isLoaded || !isHydrated) return <LoadingScreen />
  if (!isSignedIn) return <Redirect href="/sign-in" />
  if (!activeTenant) return <Redirect href="/select-troop" />
  return <Redirect href="/(tabs)/events" />
}
