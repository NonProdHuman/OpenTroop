"use client"

import { ArrowLeft, ShieldAlert } from "lucide-react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { UserButton } from "@clerk/nextjs"
import { useMe } from "@/hooks/use-me"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"

const CONSOLE_NAV = [
  { href: "/platform/tenants", label: "Tenants" },
  { href: "/platform/admins", label: "Admins" },
]

export default function PlatformLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const { data: me, isLoading, isError } = useMe()
  const authorized = Boolean(me?.platform_role)

  return (
    <div className="flex min-h-svh flex-col">
      <header className="flex h-14 items-center justify-between border-b px-4 md:px-6">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary text-primary-foreground text-xs font-bold select-none">
            OT
          </div>
          <span className="text-sm font-semibold tracking-tight">OpenTroop Platform</span>
          {me?.platform_role ? (
            <span className="ml-1 rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
              {me.platform_role}
            </span>
          ) : null}
        </div>
        {authorized ? (
          <nav className="flex items-center gap-1">
            {CONSOLE_NAV.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                  pathname.startsWith(item.href)
                    ? "bg-muted text-foreground"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                {item.label}
              </Link>
            ))}
          </nav>
        ) : null}
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" render={<Link href="/members" />}>
            <ArrowLeft className="h-4 w-4" />
            Back to app
          </Button>
          <UserButton />
        </div>
      </header>

      <main className="flex-1">
        {isLoading ? (
          <div className="space-y-3 p-6">
            <Skeleton className="h-8 w-48" />
            <Skeleton className="h-40 w-full" />
          </div>
        ) : !authorized || isError ? (
          <NotAuthorized />
        ) : (
          children
        )}
      </main>
    </div>
  )
}

function NotAuthorized() {
  return (
    <div className="mx-auto flex max-w-md flex-col items-center gap-3 px-6 py-20 text-center">
      <ShieldAlert className="h-10 w-10 text-muted-foreground" />
      <h1 className="text-lg font-semibold">Platform access required</h1>
      <p className="text-sm text-muted-foreground">
        The platform console is limited to global administrators. If you need access, ask an
        existing platform admin to grant your account a platform role.
      </p>
      <Button variant="outline" size="sm" render={<Link href="/members" />}>
        <ArrowLeft className="h-4 w-4" />
        Back to the app
      </Button>
    </div>
  )
}
