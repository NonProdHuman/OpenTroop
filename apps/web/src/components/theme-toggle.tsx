"use client"

import { useSyncExternalStore } from "react"
import { useTheme } from "next-themes"
import { Moon, Sun } from "lucide-react"
import { cn } from "@/lib/utils"

const emptySubscribe = () => () => {}

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme()
  // Avoid SSR mismatch: resolvedTheme is undefined until next-themes hydrates.
  // useSyncExternalStore reports false on the server and during the initial
  // hydration snapshot, then true on the client — no setState-in-effect needed.
  const mounted = useSyncExternalStore(
    emptySubscribe,
    () => true,
    () => false,
  )

  const isDark = mounted && resolvedTheme === "dark"

  function toggle() {
    setTheme(isDark ? "light" : "dark")
  }

  // Render a stable placeholder before mount to avoid hydration mismatch.
  if (!mounted) {
    return <div className="h-7 px-2" />
  }

  return (
    <div className="flex items-center gap-2 px-2 py-1">
      <Sun
        className={cn(
          "h-3.5 w-3.5 shrink-0 transition-opacity",
          isDark ? "opacity-35" : "opacity-90",
        )}
        style={{ color: "var(--sidebar-foreground)" }}
      />

      {/* Switch track — sidebar is always dark, so use white/opacity for the track */}
      <button
        role="switch"
        aria-checked={isDark}
        aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
        onClick={toggle}
        className={cn(
          "relative h-5 w-9 shrink-0 rounded-full border transition-colors",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring",
          isDark
            ? "border-[var(--sidebar-primary)] bg-[var(--sidebar-primary)]"
            : "border-white/25 bg-white/20",
        )}
      >
        {/* Knob */}
        <span
          className={cn(
            "absolute top-0.5 left-0.5 h-4 w-4 rounded-full bg-white shadow-sm transition-transform",
            isDark ? "translate-x-[14px]" : "translate-x-0",
          )}
        />
      </button>

      <Moon
        className={cn(
          "h-3.5 w-3.5 shrink-0 transition-opacity",
          isDark ? "opacity-90" : "opacity-35",
        )}
        style={{ color: "var(--sidebar-foreground)" }}
      />
    </div>
  )
}
