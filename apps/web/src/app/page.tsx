"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"
import { useMe } from "@/hooks/use-me"
import { useMemberships } from "@/hooks/use-memberships"
import { Loader2 } from "lucide-react"

import { getTenantRedirectUrl } from "@/lib/subdomain"

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
      router.replace("/platform/tenants")
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
    <div className="flex h-screen w-full flex-col items-center justify-center gap-4 text-center px-4">
      <h1 className="text-2xl font-semibold tracking-tight">Welcome to OpenTroop</h1>
      <p className="text-muted-foreground max-w-sm">
        You don&apos;t belong to any troops yet. Ask your troop administrator for an invitation link.
      </p>
    </div>
  )
}
