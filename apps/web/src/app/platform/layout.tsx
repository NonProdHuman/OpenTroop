"use client"

import { ArrowLeft, ShieldAlert } from "lucide-react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { useMe } from "@/hooks/use-me"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Separator } from "@/components/ui/separator"
import { AppSidebar } from "@/components/app-sidebar"
import { SidebarProvider, SidebarInset, SidebarTrigger } from "@/components/ui/sidebar"
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
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        {/* Platform sub-header: sidebar trigger + breadcrumb + Tenants/Admins tabs + back link */}
        <header className="flex h-14 shrink-0 items-center gap-2 border-b px-4 bg-background/80 backdrop-blur-sm sticky top-0 z-10">
          <SidebarTrigger className="-ml-1" />
          <Separator orientation="vertical" className="mr-1 h-4" />
          <span className="text-sm font-medium text-muted-foreground select-none">Platform</span>

          {authorized && (
            <>
              <Separator orientation="vertical" className="mx-1 h-4" />
              <nav className="flex items-center gap-0.5">
                {CONSOLE_NAV.map((item) => (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={cn(
                      "rounded-md px-3 py-1.5 text-sm font-medium transition-colors duration-100",
                      pathname.startsWith(item.href)
                        ? "bg-accent text-accent-foreground"
                        : "text-muted-foreground hover:text-foreground hover:bg-muted/60",
                    )}
                  >
                    {item.label}
                  </Link>
                ))}
              </nav>
            </>
          )}

          <div className="ml-auto">
            <Button variant="ghost" size="sm" render={<Link href="/members" />} nativeButton={false}>
              <ArrowLeft className="h-4 w-4" />
              Back to app
            </Button>
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
      </SidebarInset>
    </SidebarProvider>
  )
}

function NotAuthorized() {
  return (
    <div className="mx-auto flex max-w-md flex-col items-center gap-4 px-6 py-24 text-center">
      <div className="rounded-full bg-muted p-4">
        <ShieldAlert className="h-7 w-7 text-muted-foreground" />
      </div>
      <div className="space-y-1">
        <h1 className="text-base font-semibold">Platform access required</h1>
        <p className="text-sm text-muted-foreground">
          The platform console is limited to global administrators. If you need access, ask an
          existing platform admin to grant your account a platform role.
        </p>
      </div>
      <Button variant="outline" size="sm" render={<Link href="/members" />} nativeButton={false}>
        <ArrowLeft className="h-4 w-4" />
        Back to the app
      </Button>
    </div>
  )
}
