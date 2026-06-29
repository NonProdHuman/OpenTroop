"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"
import { useMe } from "@/hooks/use-me"
import { useMemberships } from "@/hooks/use-memberships"
import { Loader2 } from "lucide-react"

import { getTenantRedirectUrl } from "@/lib/subdomain"
import { getAdminUrl } from "@/lib/domains"
import { UserButton } from "@clerk/nextjs"
import Link from "next/link"
import { buttonVariants } from "@/components/ui/button"
import { cn } from "@/lib/utils"

export default function RootPage() {
  const router = useRouter()
  const { data: me, isLoading: meLoading } = useMe()
  const { data: memberships, isLoading: membershipsLoading } = useMemberships()

  useEffect(() => {
    if (meLoading || membershipsLoading) return

    if (memberships && memberships.length > 0) {
      const redirectUrl = getTenantRedirectUrl(memberships[0].tenant_slug, "/members")
      if (redirectUrl) {
        window.location.replace(redirectUrl)
      } else {
        router.replace("/members")
      }
    } else if (me?.platform_role) {
      window.location.replace(getAdminUrl("/tenants"))
    }
  }, [me, memberships, meLoading, membershipsLoading, router])

  if (meLoading || membershipsLoading) {
    return (
      <div className="flex h-screen w-full items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="flex h-screen w-full flex-col items-center justify-center gap-8 text-center px-4 bg-background">
      <div className="space-y-3">
        <h1 className="text-4xl font-extrabold tracking-tight lg:text-5xl">OpenTroop</h1>
        <p className="text-lg text-muted-foreground max-w-md mx-auto">
          The modern, offline-first management platform for your troop.
        </p>
      </div>

      {me ? (
        <div className="flex flex-col items-center gap-4 p-6 border rounded-xl bg-card text-card-foreground shadow-sm max-w-md">
          <UserButton showName />
          <p className="text-sm text-muted-foreground">
            You don&apos;t belong to any troops yet. Ask your troop administrator for an invitation link to get started.
          </p>
        </div>
      ) : (
        <div className="flex flex-col sm:flex-row gap-4">
          <Link href="/sign-in" className={cn(buttonVariants({ size: "lg" }), "rounded-full px-8")}>
            Sign In
          </Link>
        </div>
      )}
    </div>
  )
}
