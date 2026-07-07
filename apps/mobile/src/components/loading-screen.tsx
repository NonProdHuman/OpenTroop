import { ActivityIndicator, View } from "react-native"
import { useColors } from "@/lib/theme"

export function LoadingScreen() {
  const colors = useColors()
  return (
    <View
      style={{
        flex: 1,
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: colors.background,
      }}
    >
      <ActivityIndicator size="large" color={colors.textMuted} />
    </View>
  )
}
