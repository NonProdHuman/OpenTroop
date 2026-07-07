"use client"

import { useSyncExternalStore } from "react"
import { useTheme } from "next-themes"
import { Monitor, Moon, Sun } from "lucide-react"
import { cn } from "@/lib/utils"

const emptySubscribe = () => () => {}

const OPTIONS = [
  { value: "light", label: "Light theme", Icon: Sun },
  { value: "system", label: "Match system theme", Icon: Monitor },
  { value: "dark", label: "Dark theme", Icon: Moon },
] as const

/**
 * Sidebar theme control: Light / System / Dark.
 *
 * Deliberately three-state, not a toggle. next-themes persists whatever
 * `setTheme` receives — a binary light/dark switch permanently pins the
 * browser to an explicit theme on first use, silently ending OS light/dark
 * syncing with no way back. "System" must stay a reachable state.
 */
export function ThemeToggle() {
  const { theme, setTheme } = useTheme()
  // Avoid SSR mismatch: theme is undefined until next-themes hydrates.
  // useSyncExternalStore reports false on the server and during the initial
  // hydration snapshot, then true on the client — no setState-in-effect needed.
  const mounted = useSyncExternalStore(
    emptySubscribe,
    () => true,
    () => false,
  )

  // Render a stable placeholder before mount to avoid hydration mismatch.
  if (!mounted) {
    return <div className="h-7 px-2" />
  }

  const active = theme ?? "system"

  return (
    <div
      role="radiogroup"
      aria-label="Theme"
      className="mx-2 my-1 flex w-fit items-center gap-0.5 rounded-full border border-white/15 bg-white/10 p-0.5"
    >
      {OPTIONS.map(({ value, label, Icon }) => (
        <button
          key={value}
          role="radio"
          aria-checked={active === value}
          aria-label={label}
          title={label}
          onClick={() => setTheme(value)}
          className={cn(
            "flex h-5 w-7 items-center justify-center rounded-full transition-colors",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring",
            active === value
              ? "bg-[var(--sidebar-primary)] text-white shadow-sm"
              : "text-[var(--sidebar-foreground)] opacity-60 hover:opacity-90",
          )}
        >
          <Icon className="h-3.5 w-3.5" />
        </button>
      ))}
    </div>
  )
}
