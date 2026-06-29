"use client"

import { Suspense, useState, useEffect } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useClaimMembership } from "@/hooks/use-auth"
import { useActiveTenant } from "@/lib/tenant-context"

function ClaimForm() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const tokenParam = searchParams.get("token") || ""

  const [token, setToken] = useState(tokenParam)
  const claim = useClaimMembership()
  const { setActiveTenantId } = useActiveTenant()

  // Auto-submit if token is provided in URL
  useEffect(() => {
    if (tokenParam && !claim.isPending && !claim.isSuccess) {
      handleClaim(tokenParam)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tokenParam])

  async function handleClaim(tokenToClaim: string) {
    if (!tokenToClaim.trim()) return

    try {
      const member = await claim.mutateAsync(tokenToClaim)
      setActiveTenantId(member.tenant_id)

      // Fetch memberships to get the slug
      const res = await fetch("/api/auth/memberships")
      if (res.ok) {
        const memberships = await res.json()
        const membership = memberships.find((m: { tenant_id: string; tenant_slug: string }) => m.tenant_id === member.tenant_id)
        if (membership && membership.tenant_slug) {
          toast.success("Account claimed successfully")

          const isLocal = window.location.hostname.includes("localhost")
          const rootDomain = isLocal ? "opentroop.localhost:3000" : "opentroop.dev"
          window.location.href = `${window.location.protocol}//${membership.tenant_slug}.${rootDomain}/`
          return
        }
      }

      toast.success("Account claimed successfully")
      router.push("/")
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to claim token")
    }
  }

  function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    handleClaim(token)
  }

  return (
    <div className="mx-auto max-w-md pt-12">
      <div className="rounded-lg border bg-card text-card-foreground shadow-sm p-6">
        <h2 className="text-xl font-semibold mb-4">Claim Your Account</h2>
        <p className="text-sm text-muted-foreground mb-6">
          Enter your invite token below to join the troop. If you were given a link, this should be filled out automatically.
        </p>
        <form onSubmit={onSubmit} className="space-y-4">
          <Input
            required
            value={token}
            onChange={(e) => setToken(e.target.value)}
            placeholder="Invite token"
            disabled={claim.isPending}
          />
          <Button type="submit" className="w-full" disabled={claim.isPending || !token.trim()}>
            {claim.isPending ? "Claiming..." : "Claim Account"}
          </Button>
        </form>
      </div>
    </div>
  )
}

export default function ClaimPage() {
  return (
    <>
      <header className="flex h-14 shrink-0 items-center border-b px-4 bg-background/80 backdrop-blur-sm sticky top-0 z-10">
        <h1 className="text-base font-semibold tracking-tight">Claim Account</h1>
      </header>
      <div className="flex-1 p-4 md:p-6">
        <Suspense fallback={<div className="pt-12 text-center text-sm text-muted-foreground">Loading...</div>}>
          <ClaimForm />
        </Suspense>
      </div>
    </>
  )
}
